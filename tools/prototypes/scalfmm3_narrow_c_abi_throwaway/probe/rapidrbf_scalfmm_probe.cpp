#include "rapidrbf_scalfmm_probe.h"

#include <Eigen/Core>
#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstddef>
#include <cstring>
#include <limits>
#include <memory>
#include <mutex>
#include <new>
#include <omp.h>
#include <polatory/fmm/fmm_evaluator.hpp>
#include <polatory/fmm/fmm_symmetric_evaluator.hpp>
#include <polatory/geometry/bbox3d.hpp>
#include <polatory/rbf/cov_gaussian.hpp>
#include <polatory/types.hpp>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace {

constexpr char kScalFmmRevision[] = "0be3d74f17adb28adec7004f712f693ac8ee9901";
std::atomic<uint64_t> g_incident_id{1};

enum Stage : uint32_t {
  kStageAbi = 1,
  kStageValidation = 2,
  kStageResource = 3,
  kStagePreflight = 4,
  kStageNative = 5,
  kStageCertificate = 6,
  kStagePublication = 7
};

template <class T> bool has_header(const T *value) {
  return value != nullptr && value->struct_size == sizeof(T) &&
         value->abi_version == RRSF_ABI_V1;
}

void clear_error(rrsf_error_v1 *error) {
  if (error == nullptr) {
    return;
  }
  std::memset(error, 0, sizeof(*error));
  error->struct_size = sizeof(*error);
  error->abi_version = RRSF_ABI_V1;
  error->offending_index = RRSF_NO_INDEX;
}

uint32_t fail(rrsf_error_v1 *error, uint32_t status, uint32_t stage,
              const char *message, uint64_t index = RRSF_NO_INDEX) {
  if (has_header(error)) {
    clear_error(error);
    error->stage = stage;
    error->detail = status;
    error->offending_index = index;
    error->incident_id = g_incident_id.fetch_add(1);
    auto length = std::min(std::strlen(message), sizeof(error->message) - 1);
    std::memcpy(error->message, message, length);
  }
  return status;
}

bool checked_mul(uint64_t a, uint64_t b, uint64_t *out) {
  if (a != 0 && b > std::numeric_limits<uint64_t>::max() / a) {
    return false;
  }
  *out = a * b;
  return true;
}

bool checked_add(uint64_t a, uint64_t b, uint64_t *out) {
  if (b > std::numeric_limits<uint64_t>::max() - a) {
    return false;
  }
  *out = a + b;
  return true;
}

bool finite_span(const double *values, uint64_t count) {
  if (count != 0 && values == nullptr) {
    return false;
  }
  for (uint64_t i = 0; i < count; ++i) {
    if (!std::isfinite(values[i])) {
      return false;
    }
  }
  return true;
}

bool points_within_bbox(const double *values, uint64_t point_count,
                        uint32_t dimension, const double *bbox_min,
                        const double *bbox_max) {
  for (uint64_t row = 0; row < point_count; ++row) {
    for (uint32_t col = 0; col < dimension; ++col) {
      double value = values[row * dimension + col];
      if (value < bbox_min[col] || value > bbox_max[col]) {
        return false;
      }
    }
  }
  return true;
}

uint64_t source_channels(uint32_t action, uint32_t dim) {
  return action == RRSF_ACTION_F || action == RRSF_ACTION_H ? dim : 1;
}

uint64_t target_channels(uint32_t action, uint32_t dim) {
  return action == RRSF_ACTION_FT || action == RRSF_ACTION_H ? dim : 1;
}

uint64_t bytes_for_values(uint64_t count) {
  uint64_t bytes = 0;
  return checked_mul(count, sizeof(double), &bytes)
             ? bytes
             : std::numeric_limits<uint64_t>::max();
}

bool fits_eigen_index(uint64_t count) {
  return count <=
         static_cast<uint64_t>(std::numeric_limits<Eigen::Index>::max());
}

struct PlanBase;
struct LaneBase;

} // namespace

struct rrsf_plan {
  std::unique_ptr<PlanBase> impl;
};

struct rrsf_lane {
  std::unique_ptr<LaneBase> impl;
};

namespace {

struct LaneBase {
  virtual ~LaneBase() = default;
  virtual uint32_t run(const rrsf_run_desc_v1 &, rrsf_output_v1 &,
                       rrsf_report_v1 &, rrsf_error_v1 *) = 0;
  virtual void request_cancel() noexcept = 0;
};

struct PlanBase {
  virtual ~PlanBase() = default;
  virtual std::unique_ptr<LaneBase> open(const rrsf_lane_desc_v1 &) const = 0;
  virtual uint64_t persistent_estimate() const noexcept = 0;
};

template <int Dim> using Points = polatory::geometry::Points<Dim>;

template <int Dim> using Point = polatory::geometry::Point<Dim>;

template <int Dim>
Points<Dim> copy_points(const double *input, uint64_t count) {
  Points<Dim> points(static_cast<Eigen::Index>(count), Dim);
  for (uint64_t row = 0; row < count; ++row) {
    for (int col = 0; col < Dim; ++col) {
      points(static_cast<Eigen::Index>(row), col) =
          input[row * static_cast<uint64_t>(Dim) + col];
    }
  }
  return points;
}

polatory::VecX copy_weights(const double *input, uint64_t count) {
  polatory::VecX weights(static_cast<Eigen::Index>(count));
  for (uint64_t i = 0; i < count; ++i) {
    weights(static_cast<Eigen::Index>(i)) = input[i];
  }
  return weights;
}

template <int Dim> struct Plan;

template <int Dim> class Lane final : public LaneBase {
  using Gaussian = polatory::rbf::CovGaussian<Dim>;
  using InternalGaussian = polatory::rbf::internal::CovGaussian<Dim>;
  using Bbox = polatory::geometry::Bbox<Dim>;
  using Generic = polatory::fmm::FmmGenericEvaluatorPtr<Dim>;
  using Symmetric = polatory::fmm::FmmGenericSymmetricEvaluatorPtr<Dim>;

public:
  Lane(const Plan<Dim> &plan, const rrsf_lane_desc_v1 &desc)
      : plan_kind_(plan.plan_kind), action_(plan.action),
        geometry_(plan.geometry), thread_grant_(desc.grant.max_threads),
        transient_grant_(desc.grant.transient_bytes), rbf_(plan.rbf),
        sources_(plan.sources), targets_(plan.targets), weights_(plan.weights),
        bbox_(plan.bbox), persistent_estimate_(plan.persistent_estimate()) {
    auto *raw = dynamic_cast<InternalGaussian *>(rbf_.get_raw_pointer());
    if (raw == nullptr) {
      throw std::runtime_error("Gaussian type erasure failed");
    }

    bool symmetric = plan_kind_ == RRSF_WEIGHTS_VARY &&
                     geometry_ == RRSF_GEOMETRY_SELF &&
                     (action_ == RRSF_ACTION_A || action_ == RRSF_ACTION_H);
    if (symmetric) {
      if (action_ == RRSF_ACTION_A) {
        symmetric_ = std::make_unique<
            polatory::fmm::FmmSymmetricEvaluator<InternalGaussian>>(*raw,
                                                                    bbox_);
      } else {
        symmetric_ = std::make_unique<
            polatory::fmm::FmmHessianSymmetricEvaluator<InternalGaussian>>(
            *raw, bbox_);
      }
      symmetric_->set_points(sources_);
    } else {
      switch (action_) {
      case RRSF_ACTION_A:
        generic_ =
            std::make_unique<polatory::fmm::FmmEvaluator<InternalGaussian>>(
                *raw, bbox_);
        break;
      case RRSF_ACTION_F:
        generic_ = std::make_unique<
            polatory::fmm::FmmGradientEvaluator<InternalGaussian>>(*raw, bbox_);
        break;
      case RRSF_ACTION_FT:
        generic_ = std::make_unique<
            polatory::fmm::FmmGradientTransposeEvaluator<InternalGaussian>>(
            *raw, bbox_);
        break;
      case RRSF_ACTION_H:
        generic_ = std::make_unique<
            polatory::fmm::FmmHessianEvaluator<InternalGaussian>>(*raw, bbox_);
        break;
      default:
        throw std::invalid_argument("unsupported action");
      }
      generic_->set_source_points(sources_);
      if (plan_kind_ == RRSF_WEIGHTS_VARY) {
        generic_->set_target_points(targets_);
      } else {
        generic_->set_weights(weights_);
      }
    }
  }

  void request_cancel() noexcept override {
    try {
      std::lock_guard<std::mutex> lock(cancellation_mutex_);
      if (cancel_run_active_) {
        cancel_active_run_ = true;
      } else {
        cancel_next_run_ = true;
      }
    } catch (...) {
      emergency_cancel_.store(true, std::memory_order_release);
    }
  }

  uint32_t run(const rrsf_run_desc_v1 &desc, rrsf_output_v1 &output,
               rrsf_report_v1 &report, rrsf_error_v1 *error) override {
    if (busy_.test_and_set()) {
      return fail(error, RRSF_BUSY, kStagePreflight,
                  "lane is already executing");
    }
    struct BusyReset {
      std::atomic_flag &flag;
      ~BusyReset() { flag.clear(); }
    } busy_reset{busy_};

    try {
      {
        std::lock_guard<std::mutex> lock(cancellation_mutex_);
        cancel_run_active_ = true;
        cancel_active_run_ = cancel_next_run_;
        cancel_next_run_ = false;
      }
      struct CancellationReset {
        Lane &lane;
        ~CancellationReset() { lane.finish_cancellation_scope(); }
      } cancellation_reset{*this};

      if (poisoned_.load(std::memory_order_acquire)) {
        return fail(error, RRSF_INTERNAL_FAILURE, kStagePreflight,
                    "lane was poisoned by a prior caught native failure");
      }
      constexpr uint32_t kKnownRunFlags = RRSF_RUN_ALLOW_UNCERTIFIED_EVIDENCE |
                                          RRSF_RUN_FULL_DIRECT_DIAGNOSTIC |
                                          RRSF_RUN_FORCE_EXCEPTION_FOR_PROBE;
      if (desc.reserved != 0 || (desc.flags & ~kKnownRunFlags) != 0) {
        return fail(error, RRSF_INVALID_REQUEST, kStageValidation,
                    "reserved fields and unknown run flags must be zero");
      }
      if (cancellation_requested()) {
        return fail(error, RRSF_CANCELLED, kStagePreflight,
                    "cancellation observed before native execution");
      }
      if (!std::isfinite(desc.requested_abs_inf_budget) ||
          desc.requested_abs_inf_budget <= 0.0) {
        return fail(error, RRSF_INVALID_REQUEST, kStageValidation,
                    "requested_abs_inf_budget must be finite and positive");
      }

      uint64_t output_count = 0;
      if (plan_kind_ == RRSF_WEIGHTS_VARY) {
        uint64_t expected_weights = 0;
        if (!checked_mul(static_cast<uint64_t>(sources_.rows()),
                         source_channels(action_, Dim), &expected_weights) ||
            !fits_eigen_index(expected_weights)) {
          return fail(error, RRSF_INVALID_REQUEST, kStageValidation,
                      "changing weight layout overflows");
        }
        if (desc.changing_weights == nullptr ||
            desc.changing_weight_value_count != expected_weights ||
            desc.changing_targets != nullptr ||
            desc.changing_target_count != 0 ||
            desc.changing_target_value_count != 0 ||
            !finite_span(desc.changing_weights, expected_weights)) {
          return fail(error, RRSF_INVALID_REQUEST, kStageValidation,
                      "changing weights do not match the prepared action");
        }
        weights_ = copy_weights(desc.changing_weights, expected_weights);
        if (!checked_mul(static_cast<uint64_t>(targets_.rows()),
                         target_channels(action_, Dim), &output_count) ||
            !fits_eigen_index(output_count)) {
          return fail(error, RRSF_INVALID_REQUEST, kStageValidation,
                      "operator output layout overflows");
        }
      } else {
        uint64_t expected_targets = 0;
        if (desc.changing_target_count >
                static_cast<uint64_t>(
                    std::numeric_limits<Eigen::Index>::max()) ||
            !checked_mul(desc.changing_target_count, Dim, &expected_targets) ||
            !fits_eigen_index(expected_targets) ||
            (expected_targets != 0 && desc.changing_targets == nullptr) ||
            desc.changing_target_value_count != expected_targets ||
            desc.changing_weights != nullptr ||
            desc.changing_weight_value_count != 0 ||
            !finite_span(desc.changing_targets, expected_targets) ||
            !points_within_bbox(desc.changing_targets,
                                desc.changing_target_count, Dim,
                                bbox_.min().data(), bbox_.max().data())) {
          return fail(error, RRSF_INVALID_REQUEST, kStageValidation,
                      "changing targets do not match the prepared dimension");
        }
        uint64_t pair_count = 0;
        if (!checked_mul(static_cast<uint64_t>(sources_.rows()),
                         desc.changing_target_count, &pair_count) ||
            !fits_eigen_index(pair_count)) {
          return fail(error, RRSF_INVALID_REQUEST, kStageValidation,
                      "native source-target pair count is not representable");
        }
        targets_ =
            copy_points<Dim>(desc.changing_targets, desc.changing_target_count);
        if (!checked_mul(desc.changing_target_count,
                         target_channels(action_, Dim), &output_count) ||
            !fits_eigen_index(output_count)) {
          return fail(error, RRSF_INVALID_REQUEST, kStageValidation,
                      "field output layout overflows");
        }
      }

      uint64_t one_staging_buffer = bytes_for_values(output_count);
      uint64_t transient_estimate = 0;
      if (one_staging_buffer == std::numeric_limits<uint64_t>::max() ||
          !checked_add(one_staging_buffer, one_staging_buffer,
                       &transient_estimate)) {
        return fail(error, RRSF_INVALID_REQUEST, kStageValidation,
                    "output staging layout overflows");
      }
      if (transient_estimate > transient_grant_) {
        return fail(error, RRSF_RESOURCE_EXHAUSTED, kStageResource,
                    "staging estimate exceeds the transient grant");
      }
      if ((output_count != 0 && output.values == nullptr) ||
          output.value_capacity < output_count) {
        return fail(error, RRSF_INVALID_REQUEST, kStageValidation,
                    "output capacity is too small");
      }
      if ((desc.flags & RRSF_RUN_FORCE_EXCEPTION_FOR_PROBE) != 0) {
        throw std::runtime_error("forced throwaway probe exception");
      }

      if (output_count == 0) {
        uint32_t certificate_kind =
            (desc.flags & RRSF_RUN_FULL_DIRECT_DIAGNOSTIC) != 0
                ? RRSF_CERTIFICATE_FULL_DIRECT_DIAGNOSTIC
                : RRSF_CERTIFICATE_NONE;
        double diagnostic =
            certificate_kind == RRSF_CERTIFICATE_FULL_DIRECT_DIAGNOSTIC
                ? 0.0
                : std::numeric_limits<double>::quiet_NaN();
        fill_report(report, 0, 0, diagnostic, certificate_kind);
        if ((desc.flags & RRSF_RUN_ALLOW_UNCERTIFIED_EVIDENCE) == 0) {
          return fail(error, RRSF_CERTIFICATE_UNAVAILABLE, kStageCertificate,
                      "frozen estimator supplies no sound full-batch bound");
        }
        if (!begin_publication()) {
          return fail(error, RRSF_CANCELLED, kStagePublication,
                      "cancellation won the publication commit");
        }
        return RRSF_OK_UNCERTIFIED_EVIDENCE;
      }

      int previous_dynamic = omp_get_dynamic();
      int previous_max_threads = omp_get_max_threads();
      struct OmpSettingsReset {
        int dynamic;
        int max_threads;
        ~OmpSettingsReset() {
          omp_set_dynamic(dynamic);
          omp_set_num_threads(max_threads);
        }
      } omp_settings_reset{previous_dynamic, previous_max_threads};
      omp_set_dynamic(0);
      omp_set_num_threads(static_cast<int>(thread_grant_));
      if (generic_) {
        generic_->set_accuracy(std::numeric_limits<double>::infinity());
        if (plan_kind_ == RRSF_WEIGHTS_VARY) {
          generic_->set_weights(weights_);
        } else {
          generic_->set_target_points(targets_);
        }
      } else {
        symmetric_->set_accuracy(std::numeric_limits<double>::infinity());
        symmetric_->set_weights(weights_);
      }

      polatory::VecX staged =
          generic_ ? generic_->evaluate() : symmetric_->evaluate();
      if (staged.rows() != static_cast<Eigen::Index>(output_count) ||
          !staged.allFinite()) {
        poisoned_.store(true, std::memory_order_release);
        return fail(error, RRSF_INTERNAL_FAILURE, kStageNative,
                    "native output shape or finiteness is invalid");
      }

      double diagnostic = std::numeric_limits<double>::quiet_NaN();
      uint32_t certificate_kind = RRSF_CERTIFICATE_NONE;
      if ((desc.flags & RRSF_RUN_FULL_DIRECT_DIAGNOSTIC) != 0) {
        auto direct = direct_metric();
        diagnostic = (staged - direct).cwiseAbs().maxCoeff();
        certificate_kind = RRSF_CERTIFICATE_FULL_DIRECT_DIAGNOSTIC;
      }

      fill_report(report, output_count, transient_estimate, diagnostic,
                  certificate_kind);
      if ((desc.flags & RRSF_RUN_ALLOW_UNCERTIFIED_EVIDENCE) == 0) {
        return fail(error, RRSF_CERTIFICATE_UNAVAILABLE, kStageCertificate,
                    "frozen estimator supplies no sound full-batch bound");
      }
      if (!begin_publication()) {
        return fail(error, RRSF_CANCELLED, kStagePublication,
                    "cancellation observed only at the publication commit");
      }

      for (uint64_t i = 0; i < output_count; ++i) {
        output.values[i] = staged(static_cast<Eigen::Index>(i));
      }
      output.value_count = output_count;
      return RRSF_OK_UNCERTIFIED_EVIDENCE;
    } catch (const std::bad_alloc &) {
      poisoned_.store(true, std::memory_order_release);
      return fail(error, RRSF_RESOURCE_EXHAUSTED, kStageNative,
                  "native allocation failed");
    } catch (const std::exception &) {
      poisoned_.store(true, std::memory_order_release);
      return fail(error, RRSF_INTERNAL_FAILURE, kStageNative,
                  "caught C++ exception inside the ABI seam");
    } catch (...) {
      poisoned_.store(true, std::memory_order_release);
      return fail(error, RRSF_INTERNAL_FAILURE, kStageNative,
                  "caught unknown C++ failure inside the ABI seam");
    }
  }

private:
  bool cancellation_requested() {
    std::lock_guard<std::mutex> lock(cancellation_mutex_);
    bool requested =
        cancel_active_run_ ||
        emergency_cancel_.exchange(false, std::memory_order_acq_rel);
    if (requested) {
      cancel_active_run_ = false;
    }
    return requested;
  }

  bool begin_publication() {
    std::lock_guard<std::mutex> lock(cancellation_mutex_);
    bool requested =
        cancel_active_run_ ||
        emergency_cancel_.exchange(false, std::memory_order_acq_rel);
    cancel_active_run_ = false;
    if (!requested) {
      cancel_run_active_ = false;
    }
    return !requested;
  }

  void finish_cancellation_scope() noexcept {
    try {
      std::lock_guard<std::mutex> lock(cancellation_mutex_);
      cancel_run_active_ = false;
      cancel_active_run_ = false;
      emergency_cancel_.store(false, std::memory_order_release);
    } catch (...) {
      emergency_cancel_.store(false, std::memory_order_release);
    }
  }

  polatory::VecX direct_metric() const {
    uint64_t out_channels = target_channels(action_, Dim);
    polatory::VecX direct =
        polatory::VecX::Zero(targets_.rows() * out_channels);
    for (Eigen::Index ti = 0; ti < targets_.rows(); ++ti) {
      for (Eigen::Index si = 0; si < sources_.rows(); ++si) {
        auto diff = targets_.row(ti) - sources_.row(si);
        if (action_ == RRSF_ACTION_A) {
          direct(ti) += rbf_.evaluate(diff) * weights_(si);
        } else if (action_ == RRSF_ACTION_F) {
          auto gradient = rbf_.evaluate_gradient(diff);
          for (int col = 0; col < Dim; ++col) {
            direct(ti) -= gradient(col) * weights_(Dim * si + col);
          }
        } else if (action_ == RRSF_ACTION_FT) {
          auto gradient = rbf_.evaluate_gradient(diff);
          for (int row = 0; row < Dim; ++row) {
            direct(Dim * ti + row) += gradient(row) * weights_(si);
          }
        } else {
          auto hessian = rbf_.evaluate_hessian(diff);
          for (int row = 0; row < Dim; ++row) {
            for (int col = 0; col < Dim; ++col) {
              direct(Dim * ti + row) -=
                  hessian(row, col) * weights_(Dim * si + col);
            }
          }
        }
      }
    }
    return direct;
  }

  void fill_report(rrsf_report_v1 &report, uint64_t output_count,
                   uint64_t transient_estimate, double diagnostic,
                   uint32_t certificate_kind) const {
    std::memset(&report, 0, sizeof(report));
    report.struct_size = sizeof(report);
    report.abi_version = RRSF_ABI_V1;
    uint64_t pair_count = 0;
    if (!checked_mul(static_cast<uint64_t>(sources_.rows()),
                     static_cast<uint64_t>(targets_.rows()), &pair_count)) {
      pair_count = std::numeric_limits<uint64_t>::max();
    }
    bool symmetric = geometry_ == RRSF_GEOMETRY_SELF &&
                     plan_kind_ == RRSF_WEIGHTS_VARY &&
                     (action_ == RRSF_ACTION_A || action_ == RRSF_ACTION_H);
    bool direct =
        symmetric ? sources_.rows() < 1024 : pair_count < 1024ull * 1024ull;
    report.route = direct ? RRSF_ROUTE_LEGACY_DIRECT : RRSF_ROUTE_SCALFMM;
    report.certificate_kind = certificate_kind;
    report.configured_threads = thread_grant_;
    report.effective_threads = RRSF_UNKNOWN_U32;
    report.maximum_live_threads = RRSF_UNKNOWN_U32;
    report.flags = RRSF_REPORT_INPUTS_COPIED | RRSF_REPORT_OUTPUT_STAGED |
                   RRSF_REPORT_RESOURCE_ACCOUNTING_PARTIAL |
                   RRSF_REPORT_THREAD_ACCOUNTING_PARTIAL |
                   RRSF_REPORT_CANCELLATION_QUANTUM_UNBOUNDED |
                   RRSF_REPORT_WEIGHT_SENSITIVE_CONFIG_UNCERTIFIED;
    report.output_value_count = output_count;
    report.persistent_bytes_estimate = persistent_estimate_;
    report.transient_bytes_estimate = transient_estimate;
    report.maximum_unpolled_work = RRSF_UNBOUNDED_QUANTUM;
    report.diagnostic_abs_inf_error = diagnostic;
    std::memcpy(report.backend_revision, kScalFmmRevision,
                sizeof(kScalFmmRevision) - 1);
  }

  uint32_t plan_kind_;
  uint32_t action_;
  uint32_t geometry_;
  uint32_t thread_grant_;
  uint64_t transient_grant_;
  Gaussian rbf_;
  Points<Dim> sources_;
  Points<Dim> targets_;
  polatory::VecX weights_;
  Bbox bbox_;
  Generic generic_;
  Symmetric symmetric_;
  uint64_t persistent_estimate_;
  std::atomic<bool> poisoned_{false};
  std::mutex cancellation_mutex_;
  bool cancel_run_active_{false};
  bool cancel_active_run_{false};
  bool cancel_next_run_{false};
  std::atomic<bool> emergency_cancel_{false};
  std::atomic_flag busy_ = ATOMIC_FLAG_INIT;
};

template <int Dim> struct Plan final : PlanBase {
  using Gaussian = polatory::rbf::CovGaussian<Dim>;
  using Bbox = polatory::geometry::Bbox<Dim>;

  explicit Plan(const rrsf_plan_desc_v1 &desc)
      : plan_kind(desc.plan_kind), action(desc.action), geometry(desc.geometry),
        rbf({desc.kernel_parameters[0], desc.kernel_parameters[1]}),
        sources(copy_points<Dim>(desc.fixed_sources, desc.source_count)),
        targets(desc.plan_kind == RRSF_WEIGHTS_VARY
                    ? copy_points<Dim>(desc.fixed_targets, desc.target_count)
                    : Points<Dim>(0, Dim)),
        weights(desc.plan_kind == RRSF_TARGETS_VARY
                    ? copy_weights(desc.fixed_weights,
                                   desc.fixed_weight_value_count)
                    : polatory::VecX()),
        bbox(make_bbox(desc)) {}

  std::unique_ptr<LaneBase> open(const rrsf_lane_desc_v1 &desc) const override {
    return std::make_unique<Lane<Dim>>(*this, desc);
  }

  uint64_t persistent_estimate() const noexcept override {
    uint64_t source_bytes =
        bytes_for_values(static_cast<uint64_t>(sources.size()));
    uint64_t target_bytes =
        bytes_for_values(static_cast<uint64_t>(targets.size()));
    uint64_t weight_bytes =
        bytes_for_values(static_cast<uint64_t>(weights.size()));
    uint64_t estimate = 0;
    if (source_bytes == std::numeric_limits<uint64_t>::max() ||
        target_bytes == std::numeric_limits<uint64_t>::max() ||
        weight_bytes == std::numeric_limits<uint64_t>::max() ||
        !checked_add(source_bytes, target_bytes, &estimate) ||
        !checked_add(estimate, weight_bytes, &estimate)) {
      return std::numeric_limits<uint64_t>::max();
    }
    return estimate;
  }

  static Bbox make_bbox(const rrsf_plan_desc_v1 &desc) {
    Point<Dim> min;
    Point<Dim> max;
    for (int col = 0; col < Dim; ++col) {
      min(col) = desc.bbox_min[col];
      max(col) = desc.bbox_max[col];
    }
    return Bbox(min, max);
  }

  uint32_t plan_kind;
  uint32_t action;
  uint32_t geometry;
  Gaussian rbf;
  Points<Dim> sources;
  Points<Dim> targets;
  polatory::VecX weights;
  Bbox bbox;
};

uint32_t validate_plan(const rrsf_plan_desc_v1 &desc,
                       const rrsf_resource_grant_v1 &grant,
                       rrsf_error_v1 *error, uint64_t *estimate) {
  if (desc.reserved != 0 || grant.reserved != 0) {
    return fail(error, RRSF_INVALID_REQUEST, kStageValidation,
                "reserved fields must be zero");
  }
  if (desc.plan_kind != RRSF_WEIGHTS_VARY &&
      desc.plan_kind != RRSF_TARGETS_VARY) {
    return fail(error, RRSF_INVALID_REQUEST, kStageValidation,
                "unknown plan kind");
  }
  if (desc.dimension < 1 || desc.dimension > 3 || desc.action < RRSF_ACTION_A ||
      desc.action > RRSF_ACTION_H || desc.geometry < RRSF_GEOMETRY_SELF ||
      desc.geometry > RRSF_GEOMETRY_CROSS ||
      desc.kernel != RRSF_KERNEL_GAUSSIAN_PROBE_ONLY) {
    return fail(error, RRSF_UNSUPPORTED, kStageValidation,
                "prototype supports Gaussian actions in dimensions 1-3");
  }
  if (desc.kernel_parameter_count != 2 ||
      !finite_span(desc.kernel_parameters, 2) ||
      desc.kernel_parameters[0] < 0.0 || desc.kernel_parameters[1] <= 0.0) {
    return fail(error, RRSF_INVALID_REQUEST, kStageValidation,
                "Gaussian requires finite psill>=0 and range>0");
  }
  if (desc.source_count == 0) {
    return fail(error, RRSF_INVALID_REQUEST, kStageValidation,
                "source_count must be positive");
  }
  if (desc.source_count >
      static_cast<uint64_t>(std::numeric_limits<Eigen::Index>::max())) {
    return fail(error, RRSF_INVALID_REQUEST, kStageValidation,
                "source_count is not representable by the native evaluator");
  }
  uint64_t source_values = 0;
  if (!checked_mul(desc.source_count, desc.dimension, &source_values) ||
      !fits_eigen_index(source_values) ||
      source_values != desc.fixed_source_value_count ||
      !finite_span(desc.fixed_sources, source_values)) {
    return fail(error, RRSF_INVALID_REQUEST, kStageValidation,
                "fixed source layout is invalid");
  }
  for (uint32_t col = 0; col < desc.dimension; ++col) {
    if (!std::isfinite(desc.bbox_min[col]) ||
        !std::isfinite(desc.bbox_max[col]) ||
        desc.bbox_min[col] >= desc.bbox_max[col]) {
      return fail(error, RRSF_INVALID_REQUEST, kStageValidation,
                  "bbox must be finite and non-degenerate");
    }
  }
  if (!points_within_bbox(desc.fixed_sources, desc.source_count, desc.dimension,
                          desc.bbox_min, desc.bbox_max)) {
    return fail(error, RRSF_INVALID_REQUEST, kStageValidation,
                "fixed sources must lie inside the declared bbox");
  }

  uint64_t fixed_values = source_values;
  if (desc.plan_kind == RRSF_WEIGHTS_VARY) {
    uint64_t target_values = 0;
    if (desc.target_count == 0 ||
        desc.target_count >
            static_cast<uint64_t>(std::numeric_limits<Eigen::Index>::max()) ||
        !checked_mul(desc.target_count, desc.dimension, &target_values) ||
        !fits_eigen_index(target_values) ||
        target_values != desc.fixed_target_value_count ||
        !finite_span(desc.fixed_targets, target_values) ||
        !points_within_bbox(desc.fixed_targets, desc.target_count,
                            desc.dimension, desc.bbox_min, desc.bbox_max) ||
        desc.fixed_weights != nullptr || desc.fixed_weight_value_count != 0) {
      return fail(error, RRSF_INVALID_REQUEST, kStageValidation,
                  "operator plan requires only fixed source/target geometry");
    }
    if (desc.geometry == RRSF_GEOMETRY_SELF &&
        (desc.source_count != desc.target_count ||
         source_values != target_values ||
         !std::equal(desc.fixed_sources, desc.fixed_sources + source_values,
                     desc.fixed_targets))) {
      return fail(error, RRSF_INVALID_REQUEST, kStageValidation,
                  "self geometry requires equivalent logical points");
    }
    uint64_t pair_count = 0;
    if (!checked_mul(desc.source_count, desc.target_count, &pair_count) ||
        !fits_eigen_index(pair_count)) {
      return fail(error, RRSF_INVALID_REQUEST, kStageValidation,
                  "native source-target pair count is not representable");
    }
    if (!checked_add(fixed_values, target_values, &fixed_values)) {
      return fail(error, RRSF_INVALID_REQUEST, kStageValidation,
                  "fixed operator layout overflows");
    }
  } else {
    uint64_t expected_weights = 0;
    if (!checked_mul(desc.source_count,
                     source_channels(desc.action, desc.dimension),
                     &expected_weights) ||
        !fits_eigen_index(expected_weights)) {
      return fail(error, RRSF_INVALID_REQUEST, kStageValidation,
                  "fixed field weight layout overflows");
    }
    if (desc.geometry != RRSF_GEOMETRY_CROSS || desc.fixed_targets != nullptr ||
        desc.target_count != 0 || desc.fixed_target_value_count != 0 ||
        expected_weights != desc.fixed_weight_value_count ||
        !finite_span(desc.fixed_weights, expected_weights)) {
      return fail(
          error, RRSF_INVALID_REQUEST, kStageValidation,
          "field plan requires fixed sources/weights and cross geometry");
    }
    if (!checked_add(fixed_values, expected_weights, &fixed_values)) {
      return fail(error, RRSF_INVALID_REQUEST, kStageValidation,
                  "fixed field layout overflows");
    }
  }
  *estimate = bytes_for_values(fixed_values);
  if (*estimate == std::numeric_limits<uint64_t>::max()) {
    return fail(error, RRSF_INVALID_REQUEST, kStageValidation,
                "fixed input byte estimate overflows");
  }
  if (*estimate > grant.persistent_bytes) {
    return fail(error, RRSF_RESOURCE_EXHAUSTED, kStageResource,
                "copied fixed inputs exceed the persistent grant");
  }
  if (grant.max_threads == 0 ||
      grant.max_threads >
          static_cast<uint32_t>(std::numeric_limits<int>::max())) {
    return fail(error, RRSF_INVALID_REQUEST, kStageValidation,
                "max_threads must be representable and positive");
  }
  return RRSF_OK_CERTIFIED;
}

} // namespace

extern "C" uint32_t RRSF_CALL rrsf_plan_create_v1(
    const rrsf_plan_desc_v1 *desc, const rrsf_resource_grant_v1 *grant,
    rrsf_plan **out_plan, rrsf_error_v1 *error) {
  if (error != nullptr && !has_header(error)) {
    return RRSF_ABI_MISMATCH;
  }
  clear_error(error);
  if (!has_header(desc) || !has_header(grant) || out_plan == nullptr) {
    return fail(error, RRSF_ABI_MISMATCH, kStageAbi,
                "v1 structure size or version mismatch");
  }
  *out_plan = nullptr;
  uint64_t estimate = 0;
  uint32_t status = validate_plan(*desc, *grant, error, &estimate);
  if (status != RRSF_OK_CERTIFIED) {
    return status;
  }
  try {
    auto result = std::make_unique<rrsf_plan>();
    switch (desc->dimension) {
    case 1:
      result->impl = std::make_unique<Plan<1>>(*desc);
      break;
    case 2:
      result->impl = std::make_unique<Plan<2>>(*desc);
      break;
    case 3:
      result->impl = std::make_unique<Plan<3>>(*desc);
      break;
    default:
      return fail(error, RRSF_UNSUPPORTED, kStageValidation,
                  "unsupported dimension");
    }
    *out_plan = result.release();
    return RRSF_OK_CERTIFIED;
  } catch (const std::bad_alloc &) {
    return fail(error, RRSF_RESOURCE_EXHAUSTED, kStageResource,
                "plan allocation failed");
  } catch (const std::exception &) {
    return fail(error, RRSF_INVALID_REQUEST, kStageValidation,
                "caught plan construction exception");
  } catch (...) {
    return fail(error, RRSF_INTERNAL_FAILURE, kStageValidation,
                "caught unknown plan construction failure");
  }
}

extern "C" uint32_t RRSF_CALL rrsf_lane_open_v1(const rrsf_plan *plan,
                                                const rrsf_lane_desc_v1 *desc,
                                                rrsf_lane **out_lane,
                                                rrsf_error_v1 *error) {
  if (error != nullptr && !has_header(error)) {
    return RRSF_ABI_MISMATCH;
  }
  clear_error(error);
  if (plan == nullptr || plan->impl == nullptr || !has_header(desc) ||
      !has_header(&desc->grant) || out_lane == nullptr) {
    return fail(error, RRSF_ABI_MISMATCH, kStageAbi,
                "lane arguments or v1 header are invalid");
  }
  *out_lane = nullptr;
  if (desc->grant.reserved != 0 || desc->grant.max_threads == 0 ||
      desc->grant.max_threads >
          static_cast<uint32_t>(std::numeric_limits<int>::max())) {
    return fail(error, RRSF_INVALID_REQUEST, kStageValidation,
                "lane grant is invalid");
  }
  try {
    auto result = std::make_unique<rrsf_lane>();
    result->impl = plan->impl->open(*desc);
    *out_lane = result.release();
    return RRSF_OK_CERTIFIED;
  } catch (const std::bad_alloc &) {
    return fail(error, RRSF_RESOURCE_EXHAUSTED, kStageResource,
                "lane allocation failed");
  } catch (const std::exception &) {
    return fail(error, RRSF_INTERNAL_FAILURE, kStageNative,
                "caught lane construction exception");
  } catch (...) {
    return fail(error, RRSF_INTERNAL_FAILURE, kStageNative,
                "caught unknown lane construction failure");
  }
}

extern "C" uint32_t RRSF_CALL rrsf_lane_run_v1(rrsf_lane *lane,
                                               const rrsf_run_desc_v1 *desc,
                                               rrsf_output_v1 *output,
                                               rrsf_report_v1 *report,
                                               rrsf_error_v1 *error) {
  if (error != nullptr && !has_header(error)) {
    return RRSF_ABI_MISMATCH;
  }
  clear_error(error);
  if (lane == nullptr || lane->impl == nullptr || !has_header(desc) ||
      !has_header(output) || !has_header(report)) {
    return fail(error, RRSF_ABI_MISMATCH, kStageAbi,
                "run arguments or v1 header are invalid");
  }
  output->value_count = 0;
  return lane->impl->run(*desc, *output, *report, error);
}

extern "C" void RRSF_CALL rrsf_lane_request_cancel_v1(rrsf_lane *lane) {
  if (lane != nullptr && lane->impl != nullptr) {
    lane->impl->request_cancel();
  }
}

extern "C" void RRSF_CALL rrsf_lane_destroy_v1(rrsf_lane *lane) { delete lane; }

extern "C" void RRSF_CALL rrsf_plan_destroy_v1(rrsf_plan *plan) { delete plan; }
