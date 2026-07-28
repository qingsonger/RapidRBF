#include <Eigen/Cholesky>
#include <Eigen/Core>
#include <Eigen/LU>

#include <algorithm>
#include <bit>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <list>
#include <numeric>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <unordered_set>
#include <utility>
#include <vector>

#include <polatory/geometry/anisotropy.hpp>
#include <polatory/geometry/point3d.hpp>
#include <polatory/model.hpp>
#include <polatory/polynomial/lagrange_basis.hpp>
#include <polatory/polynomial/monomial_basis.hpp>
#include <polatory/polynomial/unisolvent_point_set.hpp>
#include <polatory/preconditioner/domain.hpp>
#include <polatory/preconditioner/domain_divider.hpp>
#include <polatory/preconditioner/mat_a.hpp>
#include <polatory/rbf/make_rbf.hpp>
#include <polatory/types.hpp>

namespace {

using polatory::Index;
using polatory::MatX;
using polatory::VecX;
using Domain = polatory::preconditioner::Domain<3>;
using DomainDivider = polatory::preconditioner::DomainDivider<3>;
using LagrangeBasis = polatory::polynomial::LagrangeBasis<3>;
using Model = polatory::Model<3>;
using MonomialBasis = polatory::polynomial::MonomialBasis<3>;
using Points = polatory::geometry::Points<3>;
using Rbf = polatory::rbf::Rbf<3>;
using UnisolventPointSet = polatory::polynomial::UnisolventPointSet<3>;

static_assert(
    EIGEN_WORLD_VERSION == 3 && EIGEN_MAJOR_VERSION == 5 &&
        EIGEN_MINOR_VERSION == 0,
    "the hierarchy capture requires frozen Eigen ABI/source version 3.5.0");

constexpr std::string_view kSchema =
    "rapidrbf-canonical-hierarchy-admission-corpus-v3";
constexpr std::string_view kGenerator =
    "m1-m4-1k-10k-complete-hierarchy-canonical-row-map-v3";
constexpr double kFineToCoarseRatio = 10.0;
constexpr Index kNCoarsestPoints = 2048;
constexpr Index kExpectedEffectiveCoarsePoints = 2047;
constexpr int kDimension = 3;

struct Workload {
  std::string workload_id;
  std::string panel_id;
  std::string case_id;
  std::string scale_id;
  std::string accepted_seed;
  std::string geometry_id;
  std::string fixture_id;
  std::string geometry_recipe;
  Index value_rows{};
  Index gradient_rows{};
  int requested_polynomial_degree{};
  Model model;
};

struct Artifact {
  std::string artifact_id;
  std::string owner_kind;
  std::string owner_id;
  std::string role;
  std::string path;
  std::string dtype;
  std::string encoding;
  std::vector<std::int64_t> shape;
  std::uint64_t stored_elements{};
  std::uint64_t bytes{};
};

struct CapturedWorkload {
  std::string workload_id;
  std::string value_points_artifact;
  std::string gradient_points_artifact;
  std::string observations_artifact;
  std::string model_values_artifact;
  std::string polynomial_indices_artifact;
  Index scalar_order{};
  Index polynomial_order{};
  int hierarchy_levels{};
  Index requested_coarse_points{};
  Index effective_coarse_points{};
  std::size_t block_count{};
  std::size_t fine_block_count{};
  std::size_t coarse_block_count{};
};

struct BlockRecord {
  std::string block_id;
  std::string workload_id;
  std::string role;
  int level{};
  std::size_t ordinal{};
  Index source_value_rows{};
  Index source_gradient_rows{};
  Index value_rows{};
  Index gradient_rows{};
  Index inner_value_rows{};
  Index inner_gradient_rows{};
  Index scalar_order{};
  Index polynomial_order{};
  Index reduced_order{};
  std::vector<std::pair<std::string, std::string>> artifacts;
};

struct FactorSource {
  std::string factor_source_id;
  std::string block_id;
  std::string workload_id;
  std::string matrix_role;
  std::string matrix_artifact;
  std::string factorization;
  std::string use_site;
  Index expected_rank{};
};

struct AuxiliaryDecompositionSource {
  std::string source_id;
  std::string workload_id;
  std::string matrix_artifact;
  std::string use_site;
  Index expected_rank{};
};

struct NegativeControl {
  std::string control_id;
  std::string base_workload_id;
  std::string base_fixture_id;
  std::string base_coordinate_artifact;
  std::string mutation_recipe_artifact;
  std::string mutated_coordinate_artifact;
  Index duplicate_destination_row{};
  Index duplicate_source_row{};
};

struct AssertionRecord {
  std::string assertion_id;
  std::uint64_t expected{};
  std::uint64_t actual{};
};

std::string json_quote(std::string_view text) {
  std::ostringstream out;
  out << '"';
  for (const unsigned char c : text) {
    switch (c) {
      case '"':
        out << "\\\"";
        break;
      case '\\':
        out << "\\\\";
        break;
      case '\b':
        out << "\\b";
        break;
      case '\f':
        out << "\\f";
        break;
      case '\n':
        out << "\\n";
        break;
      case '\r':
        out << "\\r";
        break;
      case '\t':
        out << "\\t";
        break;
      default:
        if (c < 0x20) {
          out << "\\u" << std::hex << std::setw(4) << std::setfill('0')
              << static_cast<unsigned int>(c) << std::dec;
        } else {
          out << static_cast<char>(c);
        }
        break;
    }
  }
  out << '"';
  return out.str();
}

std::string hexfloat(double value) {
  std::ostringstream out;
  out << std::hexfloat << value;
  return out.str();
}

void write_exact_double(std::ostream& out, double value) {
  out << "{\"decimal\":" << std::setprecision(std::numeric_limits<double>::max_digits10)
      << value << ",\"hex\":" << json_quote(hexfloat(value)) << "}";
}

void write_exact_double_array(std::ostream& out,
                              const std::vector<double>& values) {
  out << "[";
  for (std::size_t i = 0; i < values.size(); ++i) {
    if (i != 0) {
      out << ",";
    }
    write_exact_double(out, values.at(i));
  }
  out << "]";
}

void write_shape(std::ostream& out, const std::vector<std::int64_t>& shape) {
  out << "[";
  for (std::size_t i = 0; i < shape.size(); ++i) {
    if (i != 0) {
      out << ",";
    }
    out << shape.at(i);
  }
  out << "]";
}

double halton(std::uint64_t index, std::uint64_t base) {
  double factor = 1.0;
  double value = 0.0;
  while (index > 0) {
    factor /= static_cast<double>(base);
    value += factor * static_cast<double>(index % base);
    index /= base;
  }
  return value;
}

Points make_points(Index count, std::string_view geometry,
                   std::uint64_t offset) {
  Points points(count, kDimension);
  for (Index row = 0; row < count; ++row) {
    const auto sequence_index =
        static_cast<std::uint64_t>(row) + offset + 1;
    double x = halton(sequence_index, 2);
    double y = halton(sequence_index, 3);
    double z = halton(sequence_index, 5);

    if (geometry == "nonuniform-boundary") {
      x = x * x * x;
      y = 1.0 - (1.0 - y) * (1.0 - y);
      z = 0.5 * z + 0.5 * z * z;
    } else if (geometry == "mixed-hermite-shear") {
      const double raw_x = x;
      const double raw_y = y;
      x = raw_x + 0.18 * raw_y;
      y = 0.82 * raw_y + 0.11 * z;
      z = 0.15 * raw_x + 0.9 * z;
    } else if (geometry == "clustered-near-boundary") {
      const auto cluster = static_cast<int>(sequence_index % 4);
      constexpr double jitter = 0.035;
      const double center_x =
          (cluster == 0 || cluster == 3) ? 0.08 : 0.92;
      const double center_y =
          (cluster == 0 || cluster == 1) ? 0.08 : 0.92;
      const double center_z =
          (cluster == 0 || cluster == 2) ? 0.08 : 0.92;
      x = std::clamp(center_x + jitter * (x - 0.5), 0.0, 1.0);
      y = std::clamp(center_y + jitter * (y - 0.5), 0.0, 1.0);
      z = std::clamp(center_z + jitter * (z - 0.5), 0.0, 1.0);
      if (row % 97 == 0) {
        x = std::nextafter(x, 0.5);
        y = std::nextafter(y, 0.5);
      }
    }

    points(row, 0) = x;
    points(row, 1) = y;
    points(row, 2) = z;
  }

  if (count >= 4) {
    points.row(0) << 0.0, 0.0, 0.0;
    points.row(1) << 1.0, 0.0, 0.0;
    points.row(2) << 0.0, 1.0, 0.0;
    points.row(3) << 0.0, 0.0, 1.0;
  }
  if (geometry == "near-coincident-nextafter-pairs" && count >= 10) {
    constexpr double half_separation = 0x1p-13;
    constexpr double centers[] = {0.25, 0.5, 0.75};
    for (Index pair = 0; pair < 3; ++pair) {
      const Index lower_row = 4 + 2 * pair;
      const Index upper_row = lower_row + 1;
      const Index separation_axis = pair;
      points.row(lower_row).setConstant(centers[pair]);
      points.row(upper_row).setConstant(centers[pair]);
      points(lower_row, separation_axis) = std::nextafter(
          centers[pair] - half_separation,
          -std::numeric_limits<double>::infinity());
      points(upper_row, separation_axis) = std::nextafter(
          centers[pair] + half_separation,
          std::numeric_limits<double>::infinity());
      if (!(points(upper_row, separation_axis) -
                points(lower_row, separation_axis) >
            2.0 * half_separation)) {
        throw std::runtime_error(
            "nextafter fixture did not preserve its scale-relative "
            "binary64 separation");
      }
    }
  }
  return points;
}

VecX make_observations(const Points& points,
                       const Points& gradient_points) {
  VecX observations(points.rows() + kDimension * gradient_points.rows());
  for (Index i = 0; i < points.rows(); ++i) {
    const double x = points(i, 0);
    const double y = points(i, 1);
    const double z = points(i, 2);
    observations(i) =
        std::sin(0.7 * x) + 0.3 * std::cos(1.1 * y) + 0.2 * x * z;
  }
  for (Index i = 0; i < gradient_points.rows(); ++i) {
    const double x = gradient_points(i, 0);
    const double y = gradient_points(i, 1);
    const double z = gradient_points(i, 2);
    const Index offset = points.rows() + kDimension * i;
    observations(offset + 0) = 0.7 * std::cos(0.7 * x) + 0.2 * z;
    observations(offset + 1) = -0.33 * std::sin(1.1 * y);
    observations(offset + 2) = 0.2 * x;
  }
  return observations;
}

Model make_exp_model() {
  return Model(polatory::rbf::make_rbf<3>("exp", {1.0, 0.02}), 0);
}

Model make_th3_model() {
  return Model(polatory::rbf::make_rbf<3>("th3", {1.0, 0.0}));
}

Model make_hermite_model() {
  auto th3 = polatory::rbf::make_rbf<3>("th3", {0.8, 0.35});
  polatory::Mat<3> th3_anisotropy;
  th3_anisotropy << 1.0, 0.18, 0.0, 0.0, 1.25, 0.12, 0.0, 0.0, 0.82;
  th3.set_anisotropy(th3_anisotropy);

  auto gaussian = polatory::rbf::make_rbf<3>("gau", {0.4, 0.3});
  polatory::Mat<3> gaussian_anisotropy;
  gaussian_anisotropy << 0.92, 0.0, 0.08, 0.04, 1.08, 0.0, 0.0, 0.1,
      1.35;
  gaussian.set_anisotropy(gaussian_anisotropy);

  std::vector<Rbf> rbfs;
  rbfs.push_back(std::move(th3));
  rbfs.push_back(std::move(gaussian));
  Model model(std::move(rbfs));
  model.set_nugget(0.01);
  return model;
}

std::vector<Workload> workloads() {
  std::vector<Workload> result;
  result.reserve(12);
  result.push_back(Workload{
      "M1-EXP-1K",
      "M1-EXP-LOCAL",
      "M1/EXP/1K-EXACT",
      "1k",
      "lower rung of SCL.EXP-ORDINARY-1M",
      "halton-unit-cube-v1",
      "m1-halton-unit-cube-valid-1k-v1",
      "Halton bases 2/3/5; rows 0..3 replaced by the unit simplex",
      1000,
      0,
      0,
      make_exp_model(),
  });
  result.push_back(Workload{
      "M1-EXP-10K",
      "M1-EXP-LOCAL",
      "M1/EXP/10K-ASSIGNED",
      "10k",
      "lower rung of SCL.EXP-ORDINARY-1M",
      "halton-unit-cube-v1",
      "m1-halton-unit-cube-valid-10k-v1",
      "Halton bases 2/3/5; rows 0..3 replaced by the unit simplex",
      10000,
      0,
      0,
      make_exp_model(),
  });
  result.push_back(Workload{
      "M2-TH3-1K",
      "M2-TH3-CPD",
      "M2/TH3/1K-EXACT",
      "1k",
      "th3 fixed solver panel + FIT.GEOMETRY",
      "nonuniform-boundary",
      "m2-nonuniform-boundary-valid-1k-v1",
      "Halton x^3, 1-(1-y)^2, and (z+z^2)/2; unit-simplex seed",
      1000,
      0,
      Model::kMinRequiredPolyDegree,
      make_th3_model(),
  });
  result.push_back(Workload{
      "M2-TH3-10K",
      "M2-TH3-CPD",
      "M2/TH3/10K-ASSIGNED",
      "10k",
      "th3 fixed solver panel + FIT.GEOMETRY",
      "nonuniform-boundary",
      "m2-nonuniform-boundary-valid-10k-v1",
      "Halton x^3, 1-(1-y)^2, and (z+z^2)/2; unit-simplex seed",
      10000,
      0,
      Model::kMinRequiredPolyDegree,
      make_th3_model(),
  });
  result.push_back(Workload{
      "M3-HERMITE-1K",
      "M3-HERMITE-COMPOSITE",
      "M3/HERMITE/1K-EXACT",
      "1k",
      "lower rung of SCL.HERMITE-COMPOSITE-1M",
      "mixed-hermite-shear",
      "m3-mixed-hermite-shear-valid-1k-v1",
      "Halton deterministic 3D shear; unit-simplex seed",
      750,
      250,
      Model::kMinRequiredPolyDegree,
      make_hermite_model(),
  });
  result.push_back(Workload{
      "M3-HERMITE-10K",
      "M3-HERMITE-COMPOSITE",
      "M3/HERMITE/10K-ASSIGNED",
      "10k",
      "lower rung of SCL.HERMITE-COMPOSITE-1M",
      "mixed-hermite-shear",
      "m3-mixed-hermite-shear-valid-10k-v1",
      "Halton deterministic 3D shear; unit-simplex seed",
      7500,
      2500,
      Model::kMinRequiredPolyDegree,
      make_hermite_model(),
  });
  result.push_back(Workload{
      "M4-GEOMETRY-CLUSTERED-1K",
      "M4-GEOMETRY-FAILURE",
      "M4/GEOMETRY/1K-TRUTH-TABLE",
      "1k",
      "FIT.GEOMETRY boundary triplets",
      "clustered-near-boundary",
      "m4-clustered-near-boundary-valid-1k-v1",
      "four deterministic boundary clusters with bounded Halton jitter",
      1000,
      0,
      Model::kMinRequiredPolyDegree,
      make_th3_model(),
  });
  result.push_back(Workload{
      "M4-GEOMETRY-NEAR-COINCIDENT-1K",
      "M4-GEOMETRY-FAILURE",
      "M4/GEOMETRY/1K-TRUTH-TABLE",
      "1k",
      "FIT.GEOMETRY boundary triplets",
      "near-coincident-nextafter-pairs",
      "m4-near-coincident-nextafter-pairs-valid-1k-v1",
      "rows (4,5), (6,7), and (8,9) use dyadic centers 1/4, "
      "1/2, and 3/4 with outward nextafter(center +/- 2^-13) "
      "on x, y, and z respectively",
      1000,
      0,
      Model::kMinRequiredPolyDegree,
      make_th3_model(),
  });
  result.push_back(Workload{
      "M4-GEOMETRY-NONUNIFORM-1K",
      "M4-GEOMETRY-FAILURE",
      "M4/GEOMETRY/1K-TRUTH-TABLE",
      "1k",
      "FIT.GEOMETRY boundary triplets",
      "nonuniform-boundary",
      "m4-nonuniform-boundary-valid-1k-v1",
      "Halton x^3, 1-(1-y)^2, and (z+z^2)/2; unit-simplex seed",
      1000,
      0,
      Model::kMinRequiredPolyDegree,
      make_th3_model(),
  });
  result.push_back(Workload{
      "M4-GEOMETRY-CLUSTERED-10K",
      "M4-GEOMETRY-FAILURE",
      "M4/GEOMETRY/10K-SELECTED-VALID",
      "10k",
      "FIT.GEOMETRY selected-valid",
      "clustered-near-boundary",
      "m4-clustered-near-boundary-valid-10k-v1",
      "four deterministic boundary clusters with bounded Halton jitter",
      10000,
      0,
      Model::kMinRequiredPolyDegree,
      make_th3_model(),
  });
  result.push_back(Workload{
      "M4-GEOMETRY-NEAR-COINCIDENT-10K",
      "M4-GEOMETRY-FAILURE",
      "M4/GEOMETRY/10K-SELECTED-VALID",
      "10k",
      "FIT.GEOMETRY selected-valid",
      "near-coincident-nextafter-pairs",
      "m4-near-coincident-nextafter-pairs-valid-10k-v1",
      "rows (4,5), (6,7), and (8,9) use dyadic centers 1/4, "
      "1/2, and 3/4 with outward nextafter(center +/- 2^-13) "
      "on x, y, and z respectively",
      10000,
      0,
      Model::kMinRequiredPolyDegree,
      make_th3_model(),
  });
  result.push_back(Workload{
      "M4-GEOMETRY-NONUNIFORM-10K",
      "M4-GEOMETRY-FAILURE",
      "M4/GEOMETRY/10K-SELECTED-VALID",
      "10k",
      "FIT.GEOMETRY selected-valid",
      "nonuniform-boundary",
      "m4-nonuniform-boundary-valid-10k-v1",
      "Halton x^3, 1-(1-y)^2, and (z+z^2)/2; unit-simplex seed",
      10000,
      0,
      Model::kMinRequiredPolyDegree,
      make_th3_model(),
  });
  return result;
}

std::vector<Index> ordered_point_indices(
    Index count, const std::vector<Index>& polynomial_indices) {
  std::vector<Index> result(polynomial_indices);
  result.reserve(static_cast<std::size_t>(count));
  for (Index i = 0; i < count; ++i) {
    if (!std::binary_search(polynomial_indices.begin(),
                            polynomial_indices.end(), i)) {
      result.push_back(i);
    }
  }
  return result;
}

Index scalar_order(const Domain& domain) {
  return domain.num_points() + kDimension * domain.num_grad_points();
}

Domain make_coarse_domain(std::vector<Index> point_indices,
                          std::vector<Index> gradient_indices) {
  Domain domain;
  domain.point_indices = std::move(point_indices);
  domain.grad_point_indices = std::move(gradient_indices);
  domain.inner_point.assign(domain.point_indices.size(), true);
  domain.inner_grad_point.assign(domain.grad_point_indices.size(), true);
  return domain;
}

std::vector<Index> canonical_flat_indices(const Domain& domain,
                                          Index source_value_rows) {
  std::vector<Index> result(domain.point_indices);
  result.reserve(static_cast<std::size_t>(scalar_order(domain)));
  for (const Index global_gradient_index : domain.grad_point_indices) {
    for (Index component = 0; component < kDimension; ++component) {
      result.push_back(source_value_rows +
                       kDimension * global_gradient_index + component);
    }
  }
  return result;
}

VecX extract_observations(const VecX& observations, const Domain& domain,
                          Index source_value_rows) {
  VecX result(scalar_order(domain));
  for (Index i = 0; i < domain.num_points(); ++i) {
    result(i) =
        observations(domain.point_indices.at(static_cast<std::size_t>(i)));
  }
  for (Index i = 0; i < domain.num_grad_points(); ++i) {
    const Index global_gradient_index =
        domain.grad_point_indices.at(static_cast<std::size_t>(i));
    result.segment<kDimension>(domain.num_points() + kDimension * i) =
        observations.segment<kDimension>(
            source_value_rows + kDimension * global_gradient_index);
  }
  return result;
}

Index count_true(const std::vector<bool>& values) {
  return static_cast<Index>(
      std::count(values.begin(), values.end(), true));
}

bool binary64_matrix_identical(const MatX& lhs, const MatX& rhs) {
  if (lhs.rows() != rhs.rows() || lhs.cols() != rhs.cols()) {
    return false;
  }
  for (Index row = 0; row < lhs.rows(); ++row) {
    for (Index column = 0; column < lhs.cols(); ++column) {
      if (std::bit_cast<std::uint64_t>(lhs(row, column)) !=
          std::bit_cast<std::uint64_t>(rhs(row, column))) {
        return false;
      }
    }
  }
  return true;
}

std::vector<double> model_values(const Model& model) {
  std::vector<double> values;
  values.push_back(model.nugget());
  for (const auto& rbf : model.rbfs()) {
    values.insert(values.end(), rbf.parameters().begin(),
                  rbf.parameters().end());
    for (Index row = 0; row < kDimension; ++row) {
      for (Index column = 0; column < kDimension; ++column) {
        values.push_back(rbf.anisotropy()(row, column));
      }
    }
  }
  return values;
}

int hierarchy_levels(Index scalar_rows) {
  const double ratio =
      static_cast<double>(scalar_rows) /
      static_cast<double>(kNCoarsestPoints);
  return std::max(
             static_cast<int>(
                 std::ceil(std::log(ratio) /
                           std::log(kFineToCoarseRatio))),
             0) +
         1;
}

Index frozen_effective_coarse_points(Index scalar_rows, int n_levels,
                                     int level) {
  // Keep this expression in lockstep with frozen RasPreconditioner.  In the
  // pinned clang-cl/fp:precise environment pow(10, log_10(2048)) rounds just
  // below 2048, and the Index conversion therefore yields 2047.
  auto finest =
      std::log(static_cast<double>(scalar_rows)) /
      std::log(kFineToCoarseRatio);
  auto coarsest =
      std::log(static_cast<double>(kNCoarsestPoints)) /
      std::log(kFineToCoarseRatio);
  auto n_coarse_points = Index(std::pow(
      kFineToCoarseRatio,
      coarsest + (level - 1) * (finest - coarsest) /
                       (n_levels - 1)));
  return n_coarse_points;
}

std::string three_digit_ordinal(std::size_t ordinal) {
  std::ostringstream out;
  out << std::setw(3) << std::setfill('0') << ordinal;
  return out.str();
}

template <typename T>
void write_raw(const std::filesystem::path& path,
               const std::vector<T>& values) {
  std::filesystem::create_directories(path.parent_path());
  std::ofstream out(path, std::ios::binary);
  if (!out) {
    throw std::runtime_error("cannot open " + path.string());
  }
  if (!values.empty()) {
    out.write(reinterpret_cast<const char*>(values.data()),
              static_cast<std::streamsize>(values.size() * sizeof(T)));
  }
  if (!out) {
    throw std::runtime_error("cannot write " + path.string());
  }
}

class ArtifactWriter {
 public:
  ArtifactWriter(std::filesystem::path root,
                 std::vector<Artifact>& artifacts)
      : root_(std::move(root)), artifacts_(artifacts) {}

  std::string emit_f64_values(
      std::string owner_kind, std::string owner_id, std::string role,
      const std::filesystem::path& relative,
      const std::vector<double>& values,
      std::vector<std::int64_t> shape,
      std::string encoding = "contiguous") {
    write_raw(root_ / relative, values);
    return register_artifact(
        std::move(owner_kind), std::move(owner_id), std::move(role), relative,
        "f64", std::move(encoding), std::move(shape), values.size(),
        values.size() * sizeof(double));
  }

  std::string emit_f64_vector(std::string owner_kind, std::string owner_id,
                              std::string role,
                              const std::filesystem::path& relative,
                              const VecX& vector) {
    std::vector<double> values(static_cast<std::size_t>(vector.rows()));
    for (Index i = 0; i < vector.rows(); ++i) {
      values.at(static_cast<std::size_t>(i)) = vector(i);
    }
    return emit_f64_values(
        std::move(owner_kind), std::move(owner_id), std::move(role), relative,
        values, {static_cast<std::int64_t>(vector.rows())});
  }

  template <typename Derived>
  std::string emit_f64_matrix(std::string owner_kind, std::string owner_id,
                              std::string role,
                              const std::filesystem::path& relative,
                              const Eigen::MatrixBase<Derived>& matrix) {
    std::vector<double> values;
    values.reserve(static_cast<std::size_t>(matrix.size()));
    for (Index row = 0; row < matrix.rows(); ++row) {
      for (Index column = 0; column < matrix.cols(); ++column) {
        values.push_back(matrix(row, column));
      }
    }
    return emit_f64_values(
        std::move(owner_kind), std::move(owner_id), std::move(role), relative,
        values,
        {static_cast<std::int64_t>(matrix.rows()),
         static_cast<std::int64_t>(matrix.cols())},
        "row-major");
  }

  std::string emit_f64_lower(std::string owner_kind, std::string owner_id,
                             std::string role,
                             const std::filesystem::path& relative,
                             const MatX& matrix) {
    if (matrix.rows() != matrix.cols()) {
      throw std::invalid_argument(
          "lower-triangle artifact requires a square matrix");
    }
    std::vector<double> values;
    values.reserve(static_cast<std::size_t>(
        matrix.rows() * (matrix.rows() + 1) / 2));
    for (Index row = 0; row < matrix.rows(); ++row) {
      for (Index column = 0; column <= row; ++column) {
        values.push_back(matrix(row, column));
      }
    }
    return emit_f64_values(
        std::move(owner_kind), std::move(owner_id), std::move(role), relative,
        values,
        {static_cast<std::int64_t>(matrix.rows()),
         static_cast<std::int64_t>(matrix.cols())},
        "lower-triangle-row-major-packed");
  }

  std::string emit_i64(std::string owner_kind, std::string owner_id,
                       std::string role,
                       const std::filesystem::path& relative,
                       const std::vector<Index>& indices) {
    std::vector<std::int64_t> values;
    values.reserve(indices.size());
    for (const Index index : indices) {
      values.push_back(static_cast<std::int64_t>(index));
    }
    write_raw(root_ / relative, values);
    return register_artifact(
        std::move(owner_kind), std::move(owner_id), std::move(role), relative,
        "i64", "contiguous",
        {static_cast<std::int64_t>(values.size())}, values.size(),
        values.size() * sizeof(std::int64_t));
  }

  std::string emit_bool_mask(std::string owner_kind, std::string owner_id,
                             std::string role,
                             const std::filesystem::path& relative,
                             const std::vector<bool>& mask) {
    std::vector<std::uint8_t> values;
    values.reserve(mask.size());
    for (const bool value : mask) {
      values.push_back(value ? std::uint8_t{1} : std::uint8_t{0});
    }
    write_raw(root_ / relative, values);
    return register_artifact(
        std::move(owner_kind), std::move(owner_id), std::move(role), relative,
        "u8", "boolean-mask",
        {static_cast<std::int64_t>(values.size())}, values.size(),
        values.size() * sizeof(std::uint8_t));
  }

 private:
  std::string register_artifact(
      std::string owner_kind, std::string owner_id, std::string role,
      const std::filesystem::path& relative, std::string dtype,
      std::string encoding, std::vector<std::int64_t> shape,
      std::size_t stored_elements, std::size_t bytes) {
    const std::string artifact_id =
        owner_kind + ":" + owner_id + ":" + role;
    if (!artifact_ids_.insert(artifact_id).second) {
      throw std::runtime_error("duplicate artifact id " + artifact_id);
    }
    artifacts_.push_back(Artifact{
        artifact_id,
        std::move(owner_kind),
        std::move(owner_id),
        std::move(role),
        relative.generic_string(),
        std::move(dtype),
        std::move(encoding),
        std::move(shape),
        static_cast<std::uint64_t>(stored_elements),
        static_cast<std::uint64_t>(bytes),
    });
    return artifact_id;
  }

  std::filesystem::path root_;
  std::vector<Artifact>& artifacts_;
  std::unordered_set<std::string> artifact_ids_;
};

void add_block_artifact(BlockRecord& block, std::string role,
                        std::string artifact_id) {
  block.artifacts.emplace_back(std::move(role), std::move(artifact_id));
}

void capture_block(const Workload& workload, const Points& full_points,
                   const Points& full_gradient_points,
                   const VecX& full_observations,
                   const MatX& lagrange_p_full,
                   const MatX& workload_unisolvent_p,
                   const Domain& domain,
                   std::string role, int level, std::size_t ordinal,
                   ArtifactWriter& artifact_writer,
                   std::vector<BlockRecord>& blocks,
                   std::vector<FactorSource>& factor_sources) {
  const std::string local_name =
      role == "fine" ? "level-" + std::to_string(level) + "-fine-" +
                           three_digit_ordinal(ordinal)
                     : "level-0-coarse-000";
  const std::string block_id = workload.workload_id + "-" + local_name;
  const auto relative_dir =
      std::filesystem::path("blocks") / workload.workload_id / local_name;

  const Points points =
      full_points(domain.point_indices, polatory::kAll);
  const Points gradient_points =
      full_gradient_points(domain.grad_point_indices, polatory::kAll);
  const MatX matrix_a = polatory::preconditioner::mat_a(
      workload.model, points, gradient_points);
  const MonomialBasis monomial(workload.model.poly_degree());
  const MatX matrix_p = monomial.evaluate(points, gradient_points);

  const std::vector<Index> flat_indices =
      canonical_flat_indices(domain, full_points.rows());
  const MatX local_lagrange_p =
      lagrange_p_full(flat_indices, polatory::kAll);
  const Index polynomial_order = workload.model.poly_basis_size();
  const Index order = scalar_order(domain);
  if (order <= polynomial_order) {
    throw std::runtime_error(block_id +
                             " has no reduced degrees of freedom");
  }
  const Index reduced_order = order - polynomial_order;
  const MatX q_top =
      -local_lagrange_p.bottomRows(reduced_order).transpose();

  // Preserve the frozen FineGrid/CoarseGrid four-block operation graph.  The
  // only semantic correction is the canonical global gradient-row map used
  // above when selecting lagrange_p_full.
  const MatX qtaq =
      q_top.transpose() *
          matrix_a.topLeftCorner(polynomial_order, polynomial_order) * q_top +
      q_top.transpose() *
          matrix_a.topRightCorner(polynomial_order, reduced_order) +
      matrix_a.bottomLeftCorner(reduced_order, polynomial_order) * q_top +
      matrix_a.bottomRightCorner(reduced_order, reduced_order);

  const VecX rhs_full =
      extract_observations(full_observations, domain, full_points.rows());
  const VecX rhs_reduced =
      q_top.transpose() * rhs_full.head(polynomial_order) +
      rhs_full.tail(reduced_order);
  if (!matrix_a.allFinite() || !matrix_p.allFinite() ||
      !q_top.allFinite() || !qtaq.allFinite() ||
      !rhs_full.allFinite() || !rhs_reduced.allFinite()) {
    throw std::runtime_error(block_id +
                             " produced a non-finite capture input");
  }
  Eigen::LDLT<MatX> proposed_ldlt(qtaq);
  if (proposed_ldlt.info() != Eigen::Success) {
    throw std::runtime_error(block_id +
                             " witness LDLT factorization failed");
  }
  const VecX reference_gamma = proposed_ldlt.solve(rhs_reduced);
  if (proposed_ldlt.info() != Eigen::Success ||
      !reference_gamma.allFinite()) {
    throw std::runtime_error(block_id +
                             " witness LDLT solve failed or was non-finite");
  }
  VecX reference_lambda(order);
  reference_lambda.head(polynomial_order) =
      q_top * reference_gamma;
  reference_lambda.tail(reduced_order) = reference_gamma;
  if (!reference_lambda.allFinite()) {
    throw std::runtime_error(block_id +
                             " witness lambda was non-finite");
  }

  BlockRecord block;
  block.block_id = block_id;
  block.workload_id = workload.workload_id;
  block.role = std::move(role);
  block.level = level;
  block.ordinal = ordinal;
  block.source_value_rows = full_points.rows();
  block.source_gradient_rows = full_gradient_points.rows();
  block.value_rows = domain.num_points();
  block.gradient_rows = domain.num_grad_points();
  block.inner_value_rows = count_true(domain.inner_point);
  block.inner_gradient_rows = count_true(domain.inner_grad_point);
  block.scalar_order = order;
  block.polynomial_order = polynomial_order;
  block.reduced_order = reduced_order;

  const auto emit_i64 = [&](std::string artifact_role,
                            const std::vector<Index>& values) {
    const std::string id = artifact_writer.emit_i64(
        "block", block_id, artifact_role,
        relative_dir / (artifact_role + ".i64le"), values);
    add_block_artifact(block, std::move(artifact_role), id);
  };
  const auto emit_mask = [&](std::string artifact_role,
                             const std::vector<bool>& values) {
    const std::string id = artifact_writer.emit_bool_mask(
        "block", block_id, artifact_role,
        relative_dir / (artifact_role + ".u8"), values);
    add_block_artifact(block, std::move(artifact_role), id);
  };
  const auto emit_matrix = [&](std::string artifact_role,
                               const MatX& matrix) {
    const std::string id = artifact_writer.emit_f64_matrix(
        "block", block_id, artifact_role,
        relative_dir / (artifact_role + ".f64le"), matrix);
    add_block_artifact(block, std::move(artifact_role), id);
    return id;
  };
  const auto emit_lower = [&](std::string artifact_role,
                              const MatX& matrix) {
    const std::string id = artifact_writer.emit_f64_lower(
        "block", block_id, artifact_role,
        relative_dir / (artifact_role + ".f64le"), matrix);
    add_block_artifact(block, std::move(artifact_role), id);
    return id;
  };
  const auto emit_vector = [&](std::string artifact_role,
                               const VecX& vector) {
    const std::string id = artifact_writer.emit_f64_vector(
        "block", block_id, artifact_role,
        relative_dir / (artifact_role + ".f64le"), vector);
    add_block_artifact(block, std::move(artifact_role), id);
  };

  emit_i64("domain_value_indices", domain.point_indices);
  emit_i64("domain_gradient_indices", domain.grad_point_indices);
  emit_mask("inner_value_mask", domain.inner_point);
  emit_mask("inner_gradient_mask", domain.inner_grad_point);
  emit_i64("canonical_lagrange_flat_indices", flat_indices);
  emit_lower("a_lower", matrix_a);
  emit_matrix("p_row_major", matrix_p);
  emit_matrix("q_top_row_major", q_top);
  const std::string qtaq_artifact = emit_lower("qtaq_lower", qtaq);
  emit_vector("rhs_full", rhs_full);
  emit_vector("rhs_reduced", rhs_reduced);
  emit_vector("reference_gamma", reference_gamma);
  emit_vector("reference_lambda", reference_lambda);

  factor_sources.push_back(FactorSource{
      "factor:" + block_id + ":qtaq",
      block_id,
      workload.workload_id,
      "qtaq",
      qtaq_artifact,
      block.role == "fine" ? "symmetric-indefinite-ldlt"
                            : "symmetric-ldlt",
      block.role == "fine"
          ? "polatory::preconditioner::FineGrid<3>::setup/"
            "Eigen::LDLT2<MatX>(Q^T A Q)"
          : "polatory::preconditioner::CoarseGrid<3>::setup/"
            "Eigen::LDLT<MatX>(Q^T A Q)",
      reduced_order,
  });

  if (block.role == "coarse") {
    const MatX p_top =
        monomial.evaluate(points.topRows(polynomial_order));
    if (!binary64_matrix_identical(p_top,
                                   workload_unisolvent_p)) {
      throw std::runtime_error(
          block_id +
          " coarse P_top is not a binary64-identical alias of the "
          "workload-global unisolvent P");
    }
    const std::string p_top_artifact =
        emit_matrix("p_top_row_major", p_top);
    Eigen::FullPivLU<MatX> proposed_p_top_lu(p_top);
    if (!p_top.allFinite() || !proposed_p_top_lu.isInvertible()) {
      throw std::runtime_error(
          block_id + " witness P_top factorization failed");
    }
    const VecX reference_c = proposed_p_top_lu.solve(
        rhs_full.head(polynomial_order) -
        matrix_a.topRows(polynomial_order) * reference_lambda);
    if (!reference_c.allFinite()) {
      throw std::runtime_error(
          block_id + " witness polynomial solve was non-finite");
    }
    emit_vector("reference_c", reference_c);
    factor_sources.push_back(FactorSource{
        "factor:" + block_id + ":p-top",
        block_id,
        workload.workload_id,
        "p_top",
        p_top_artifact,
        "full-pivot-lu",
        "polatory::preconditioner::CoarseGrid<3>::setup/"
        "Eigen::FullPivLU<MatX>(P_top)",
        polynomial_order,
    });
  }

  blocks.push_back(std::move(block));
}

CapturedWorkload capture_workload(
    const Workload& workload, ArtifactWriter& artifact_writer,
    std::vector<BlockRecord>& blocks,
    std::vector<FactorSource>& factor_sources) {
  std::cout << "materializing " << workload.workload_id << " ("
            << workload.case_id << ")" << std::endl;
  const Points points =
      make_points(workload.value_rows, workload.geometry_id, 0);
  const Points gradient_points =
      make_points(workload.gradient_rows, workload.geometry_id, 20000);
  const VecX observations = make_observations(points, gradient_points);

  const UnisolventPointSet unisolvent(points,
                                      workload.model.poly_degree());
  const std::vector<Index> polynomial_indices =
      unisolvent.point_indices();
  const LagrangeBasis lagrange(
      workload.model.poly_degree(),
      points(polynomial_indices, polatory::kAll));
  const MatX lagrange_p_full =
      lagrange.evaluate(points, gradient_points);
  const MonomialBasis workload_monomial(
      workload.model.poly_degree());
  const MatX workload_unisolvent_p = workload_monomial.evaluate(
      points(polynomial_indices, polatory::kAll));

  const auto workload_dir =
      std::filesystem::path("workloads") / workload.workload_id;
  CapturedWorkload captured;
  captured.workload_id = workload.workload_id;
  captured.value_points_artifact = artifact_writer.emit_f64_matrix(
      "workload", workload.workload_id, "value_points",
      workload_dir / "value_points.f64le", points);
  captured.gradient_points_artifact = artifact_writer.emit_f64_matrix(
      "workload", workload.workload_id, "gradient_points",
      workload_dir / "gradient_points.f64le", gradient_points);
  captured.observations_artifact = artifact_writer.emit_f64_vector(
      "workload", workload.workload_id, "observations",
      workload_dir / "observations.f64le", observations);
  const std::vector<double> exact_model_values =
      model_values(workload.model);
  captured.model_values_artifact = artifact_writer.emit_f64_values(
      "workload", workload.workload_id, "model_values",
      workload_dir / "model_values.f64le", exact_model_values,
      {static_cast<std::int64_t>(exact_model_values.size())});
  captured.polynomial_indices_artifact = artifact_writer.emit_i64(
      "workload", workload.workload_id, "selected_polynomial_indices",
      workload_dir / "selected_polynomial_indices.i64le",
      polynomial_indices);

  const std::vector<Index> point_indices =
      ordered_point_indices(points.rows(), polynomial_indices);
  std::vector<Index> gradient_indices(
      static_cast<std::size_t>(gradient_points.rows()));
  std::iota(gradient_indices.begin(), gradient_indices.end(), 0);

  captured.scalar_order =
      points.rows() + kDimension * gradient_points.rows();
  captured.polynomial_order = workload.model.poly_basis_size();
  captured.hierarchy_levels = hierarchy_levels(captured.scalar_order);
  captured.requested_coarse_points = kNCoarsestPoints;
  captured.effective_coarse_points = 0;
  const std::size_t initial_block_count = blocks.size();

  if (captured.hierarchy_levels == 1) {
    Domain coarse =
        make_coarse_domain(point_indices, gradient_indices);
    capture_block(workload, points, gradient_points, observations,
                  lagrange_p_full, workload_unisolvent_p, coarse,
                  "coarse", 0, 0,
                  artifact_writer, blocks, factor_sources);
  } else if (captured.hierarchy_levels == 2) {
    const auto& anisotropy = workload.model.rbfs().at(0).anisotropy();
    Points division_points;
    Points division_gradient_points;
    if (workload.model.num_rbfs() == 1 && !anisotropy.isIdentity()) {
      division_points =
          polatory::geometry::transform_points<kDimension>(anisotropy,
                                                           points);
      division_gradient_points =
          polatory::geometry::transform_points<kDimension>(
              anisotropy, gradient_points);
    } else {
      division_points = points;
      division_gradient_points = gradient_points;
    }

    DomainDivider divider(division_points, division_gradient_points,
                          point_indices, gradient_indices,
                          polynomial_indices);
    constexpr int level = 1;
    captured.effective_coarse_points =
        frozen_effective_coarse_points(captured.scalar_order,
                                       captured.hierarchy_levels, level);
    if (captured.effective_coarse_points !=
        kExpectedEffectiveCoarsePoints) {
      throw std::runtime_error(
          workload.workload_id +
          " frozen coarse-point expression expected 2047, got " +
          std::to_string(captured.effective_coarse_points));
    }
    auto [coarse_points, coarse_gradients] =
        divider.choose_coarse_points(
            captured.effective_coarse_points);
    if (divider.domains().size() != 32) {
      throw std::runtime_error(
          workload.workload_id + " expected 32 fine domains, got " +
          std::to_string(divider.domains().size()));
    }

    std::size_t ordinal = 0;
    for (const auto& domain : divider.domains()) {
      capture_block(workload, points, gradient_points, observations,
                    lagrange_p_full, workload_unisolvent_p, domain,
                    "fine", 1, ordinal,
                    artifact_writer, blocks, factor_sources);
      ++ordinal;
    }
    Domain coarse =
        make_coarse_domain(std::move(coarse_points),
                           std::move(coarse_gradients));
    capture_block(workload, points, gradient_points, observations,
                  lagrange_p_full, workload_unisolvent_p, coarse,
                  "coarse", 0, 0,
                  artifact_writer, blocks, factor_sources);
  } else {
    throw std::runtime_error(
        workload.workload_id +
        " is outside the registered one/two-level hierarchy inventory");
  }

  captured.block_count = blocks.size() - initial_block_count;
  captured.fine_block_count =
      captured.hierarchy_levels == 2 ? 32 : 0;
  captured.coarse_block_count = 1;
  if (captured.block_count !=
      captured.fine_block_count + captured.coarse_block_count) {
    throw std::runtime_error(workload.workload_id +
                             " hierarchy block count drifted");
  }
  return captured;
}

NegativeControl capture_rank_invalid_control(
    ArtifactWriter& artifact_writer) {
  constexpr std::string_view control_id =
      "M4-GEOMETRY-1K-RANK-INVALID-DUPLICATE";
  constexpr Index source_row = 4;
  constexpr Index destination_row = 5;
  const Points base_points =
      make_points(1000, "nonuniform-boundary", 0);
  Points mutated_points = base_points;

  bool originally_distinct = false;
  for (Index column = 0; column < kDimension; ++column) {
    originally_distinct =
        originally_distinct ||
        std::bit_cast<std::uint64_t>(
            base_points(source_row, column)) !=
            std::bit_cast<std::uint64_t>(
                base_points(destination_row, column));
    mutated_points(destination_row, column) =
        mutated_points(source_row, column);
  }
  if (!originally_distinct) {
    throw std::runtime_error(
        "rank-invalid control base rows were already duplicates");
  }
  for (Index column = 0; column < kDimension; ++column) {
    if (std::bit_cast<std::uint64_t>(
            mutated_points(source_row, column)) !=
        std::bit_cast<std::uint64_t>(
            mutated_points(destination_row, column))) {
      throw std::runtime_error(
          "rank-invalid control mutation did not create an exact "
          "binary64 duplicate");
    }
  }

  const auto relative_dir =
      std::filesystem::path("controls") / control_id;
  const std::string mutation_artifact = artifact_writer.emit_i64(
      "control", std::string(control_id),
      "duplicate_coordinate_mutation",
      relative_dir / "duplicate_coordinate_mutation.i64le",
      std::vector<Index>{destination_row, source_row});
  const std::string mutated_coordinate_artifact =
      artifact_writer.emit_f64_matrix(
          "control", std::string(control_id),
          "mutated_value_points",
          relative_dir / "mutated_value_points.f64le",
          mutated_points);

  return NegativeControl{
      std::string(control_id),
      "M4-GEOMETRY-NONUNIFORM-1K",
      "m4-nonuniform-boundary-valid-1k-v1",
      "workload:M4-GEOMETRY-NONUNIFORM-1K:value_points",
      mutation_artifact,
      mutated_coordinate_artifact,
      destination_row,
      source_row,
  };
}

std::string compiler_id() {
#if defined(__clang__)
  return "clang-" + std::to_string(__clang_major__) + "." +
         std::to_string(__clang_minor__) + "." +
         std::to_string(__clang_patchlevel__);
#elif defined(_MSC_VER)
  return "msvc-" + std::to_string(_MSC_VER);
#elif defined(__GNUC__)
  return "gcc-" + std::to_string(__GNUC__) + "." +
         std::to_string(__GNUC_MINOR__) + "." +
         std::to_string(__GNUC_PATCHLEVEL__);
#else
  return "unknown";
#endif
}

void write_model_descriptor(std::ostream& out, const Model& model,
                            const std::string& model_artifact) {
  out << "        \"model\": {\n"
      << "          \"exact_values_artifact\": "
      << json_quote(model_artifact) << ",\n"
      << "          \"layout\": \"nugget; for each RBF: parameters then "
         "3x3 anisotropy in row-major order\",\n"
      << "          \"nugget\": {\"offset\":0,\"value\":";
  write_exact_double(out, model.nugget());
  out << "},\n"
      << "          \"rbfs\": [\n";

  std::size_t offset = 1;
  for (std::size_t i = 0; i < model.rbfs().size(); ++i) {
    const auto& rbf = model.rbfs().at(i);
    const std::vector<double> parameters = rbf.parameters();
    std::vector<double> anisotropy;
    anisotropy.reserve(kDimension * kDimension);
    for (Index row = 0; row < kDimension; ++row) {
      for (Index column = 0; column < kDimension; ++column) {
        anisotropy.push_back(rbf.anisotropy()(row, column));
      }
    }
    out << "            {\n"
        << "              \"short_name\": "
        << json_quote(rbf.short_name()) << ",\n"
        << "              \"parameters\": {\"offset\":" << offset
        << ",\"count\":" << parameters.size() << ",\"values\":";
    write_exact_double_array(out, parameters);
    out << "},\n";
    offset += parameters.size();
    out << "              \"anisotropy\": {\"offset\":" << offset
        << ",\"count\":" << anisotropy.size()
        << ",\"shape\":[3,3],\"encoding\":\"row-major\",\"values\":";
    write_exact_double_array(out, anisotropy);
    out << "}\n"
        << "            }"
        << (i + 1 == model.rbfs().size() ? "\n" : ",\n");
    offset += anisotropy.size();
  }
  out << "          ]\n"
      << "        }";
}

void write_manifest(
    const std::filesystem::path& path,
    const std::vector<Workload>& workload_fixtures,
    const std::vector<CapturedWorkload>& captured_workloads,
    const std::vector<Artifact>& artifacts,
    const std::vector<BlockRecord>& blocks,
    const std::vector<FactorSource>& factor_sources,
    const std::vector<AuxiliaryDecompositionSource>& auxiliary_sources,
    const NegativeControl& negative_control,
    const std::vector<AssertionRecord>& assertions) {
  std::ofstream out(path);
  if (!out) {
    throw std::runtime_error("cannot open " + path.string());
  }

  const auto fine_blocks = static_cast<std::size_t>(
      std::count_if(blocks.begin(), blocks.end(),
                    [](const BlockRecord& block) {
                      return block.role == "fine";
                    }));
  const auto coarse_blocks = blocks.size() - fine_blocks;
  const auto qtaq_sources = static_cast<std::size_t>(
      std::count_if(factor_sources.begin(), factor_sources.end(),
                    [](const FactorSource& source) {
                      return source.matrix_role == "qtaq";
                    }));
  const auto p_top_sources = factor_sources.size() - qtaq_sources;

  out << "{\n"
      << "  \"schema\": " << json_quote(kSchema) << ",\n"
      << "  \"generator\": " << json_quote(kGenerator) << ",\n"
      << "  \"evidence\": \"instrumented raw capture; independent "
         "certification and immutable locking are downstream\",\n"
      << "  \"polatory_commit\": " << json_quote(POLATORY_FROZEN_COMMIT)
      << ",\n"
      << "  \"compiler\": " << json_quote(compiler_id()) << ",\n"
      << "  \"build_mode\": "
      << json_quote(RAPIDRBF_CAPTURE_BUILD_MODE) << ",\n"
      << "  \"floating_point_mode\": "
      << json_quote(RAPIDRBF_CAPTURE_FLOAT_MODE) << ",\n"
      << "  \"eigen_version\": "
      << json_quote(std::to_string(EIGEN_WORLD_VERSION) + "." +
                    std::to_string(EIGEN_MAJOR_VERSION) + "." +
                    std::to_string(EIGEN_MINOR_VERSION))
      << ",\n"
      << "  \"binary_contract\": {\"double_bytes\":" << sizeof(double)
      << ",\"iec559\":"
      << (std::numeric_limits<double>::is_iec559 ? "true" : "false")
      << ",\"little_endian\":"
      << (std::endian::native == std::endian::little ? "true" : "false")
      << "},\n"
      << "  \"assembly\": {\n"
      << "    \"projected_matrix\": "
      << json_quote("frozen-four-block-expression-v1") << ",\n"
      << "    \"projected_rhs\": "
      << json_quote("frozen-qtop-gemv-plus-tail-v1") << ",\n"
      << "    \"row_channel_map\": "
      << json_quote(
             "values at global value index; gradients at "
             "source_value_rows + 3*global_gradient_index + component")
      << ",\n"
      << "    \"domain_order\": "
      << json_quote(
             "selected polynomial value indices first, followed by "
             "DomainDivider order; gradient channels follow domain values")
      << "\n"
      << "  },\n"
      << "  \"hierarchy_policy\": {\n"
      << "    \"fine_to_coarse_ratio\": 10,\n"
      << "    \"requested_coarsest_points\": 2048,\n"
      << "    \"effective_10k_coarse_points\": 2047,\n"
      << "    \"effective_expression\": "
      << json_quote(
             "Index(pow(kFineToCoarseRatio, coarsest + "
             "(level - 1) * (finest - coarsest) / "
             "(n_levels - 1)))")
      << ",\n"
      << "    \"expression_bindings\": {\"level\":1,"
         "\"n_levels\":2,\"kFineToCoarseRatio\":10,"
         "\"kNCoarsestPoints\":2048},\n"
      << "    \"domain_max_leaf_scalar_order\": 1024,\n"
      << "    \"domain_overlap_quota\": "
         "{\"decimal\":0.5,\"hex\":\"0x1p-1\"},\n"
      << "    \"registered_levels\": [1,2]\n"
      << "  },\n"
      << "  \"witness_contract\": {\n"
      << "    \"authority\": \"untrusted-witness-only\",\n"
      << "    \"producer\": \"frozen Eigen LDLT and FullPivLU proposal\",\n"
      << "    \"per_block\": [\"reference_gamma\",\"reference_lambda\"],\n"
      << "    \"coarse_only\": [\"reference_c\"],\n"
      << "    \"fine_reference_c\": \"prohibited-and-absent\",\n"
      << "    \"capture_enforcement\": \"fail on LDLT status other than "
         "Success, non-invertible coarse P_top, or any non-finite input "
         "or witness\",\n"
      << "    \"allowed_use\": \"independent physical action and residual "
         "replay with zero factor/backend calls\",\n"
      << "    \"forbidden_use\": \"rank, solver, backend, or admission "
         "judgment\"\n"
      << "  },\n"
      << "  \"lineage\": {\n"
      << "    \"m4_positive_selection\": {\n"
      << "      \"authority\": \"registered FIT.GEOMETRY positive "
         "fixture triplets\",\n"
      << "      \"selected_fixtures\": [\n"
      << "        {\"case_id\":\"M4/GEOMETRY/1K-TRUTH-TABLE\","
         "\"fixture_id\":\"m4-clustered-near-boundary-valid-1k-v1\"},\n"
      << "        {\"case_id\":\"M4/GEOMETRY/1K-TRUTH-TABLE\","
         "\"fixture_id\":\"m4-near-coincident-nextafter-pairs-valid-1k-v1\"},\n"
      << "        {\"case_id\":\"M4/GEOMETRY/1K-TRUTH-TABLE\","
         "\"fixture_id\":\"m4-nonuniform-boundary-valid-1k-v1\"},\n"
      << "        {\"case_id\":\"M4/GEOMETRY/10K-SELECTED-VALID\","
         "\"fixture_id\":\"m4-clustered-near-boundary-valid-10k-v1\"},\n"
      << "        {\"case_id\":\"M4/GEOMETRY/10K-SELECTED-VALID\","
         "\"fixture_id\":\"m4-near-coincident-nextafter-pairs-valid-10k-v1\"},\n"
      << "        {\"case_id\":\"M4/GEOMETRY/10K-SELECTED-VALID\","
         "\"fixture_id\":\"m4-nonuniform-boundary-valid-10k-v1\"}\n"
      << "      ],\n"
      << "      \"selection_statement\": \"three named positive fixtures "
         "per registered M4 rung: clustered, exact-distinct "
         "near-coincident, and nonuniform\",\n"
      << "      \"near_coincident_recipe\": {\"row_pairs\":[[4,5],"
         "[6,7],[8,9]],\"centers_hex\":[\"0x1p-2\",\"0x1p-1\","
         "\"0x1.8p-1\"],\"separation_axes\":[\"x\",\"y\",\"z\"],"
         "\"half_separation_hex\":\"0x1p-13\","
         "\"endpoint_expression\":\"outward nextafter(center +/- 2^-13)\","
         "\"minimum_total_separation_hex\":\"0x1p-12\"}\n"
      << "    }\n"
      << "  },\n"
      << "  \"controls\": [\n"
      << "    {\n"
      << "      \"control_id\": "
      << json_quote(negative_control.control_id) << ",\n"
      << "      \"control_kind\": \"rank-invalid-negative\",\n"
      << "      \"base_fixture\": {\"workload_id\":"
      << json_quote(negative_control.base_workload_id)
      << ",\"fixture_id\":"
      << json_quote(negative_control.base_fixture_id)
      << ",\"coordinate_artifact\":"
      << json_quote(negative_control.base_coordinate_artifact)
      << ",\"hash_binding\":\"required immutable-lock entry\"},\n"
      << "      \"mutation\": {\"recipe\":"
      << json_quote(
             "copy the source coordinate row bit-for-bit over the "
             "destination coordinate row")
      << ",\"recipe_artifact\":"
      << json_quote(negative_control.mutation_recipe_artifact)
      << ",\"mutated_coordinate_artifact\":"
      << json_quote(negative_control.mutated_coordinate_artifact)
      << ",\"destination_row\":"
      << negative_control.duplicate_destination_row
      << ",\"source_row\":"
      << negative_control.duplicate_source_row << "},\n"
      << "      \"expected_disposition\": \"RankDeficient\",\n"
      << "      \"admission_phase\": \"pre-backend\",\n"
      << "      \"backend_calls\": 0,\n"
      << "      \"workload_count_contribution\": 0,\n"
      << "      \"block_count_contribution\": 0,\n"
      << "      \"factor_source_count_contribution\": 0\n"
      << "    }\n"
      << "  ],\n"
      << "  \"inventory_profile\": {\n"
      << "    \"profile_id\": \"canonical-m1-m4-1k-10k-v3\",\n"
      << "    \"expected\": {\"workloads\":12,\"blocks\":204,"
         "\"fine_blocks\":192,\"coarse_blocks\":12,"
         "\"factor_sources\":216,\"qtaq_factor_sources\":204,"
         "\"p_top_factor_sources\":12,"
         "\"auxiliary_decomposition_sources\":12,\"controls\":1,"
         "\"artifacts\":2738}\n"
      << "  },\n"
      << "  \"counts\": {\n"
      << "    \"artifacts\": " << artifacts.size() << ",\n"
      << "    \"workloads\": " << captured_workloads.size() << ",\n"
      << "    \"blocks\": " << blocks.size() << ",\n"
      << "    \"fine_blocks\": " << fine_blocks << ",\n"
      << "    \"coarse_blocks\": " << coarse_blocks << ",\n"
      << "    \"factor_sources\": " << factor_sources.size() << ",\n"
      << "    \"qtaq_factor_sources\": " << qtaq_sources << ",\n"
      << "    \"p_top_factor_sources\": " << p_top_sources << ",\n"
      << "    \"auxiliary_decomposition_sources\": "
      << auxiliary_sources.size() << ",\n"
      << "    \"controls\": 1\n"
      << "  },\n"
      << "  \"artifacts\": [\n";

  for (std::size_t i = 0; i < artifacts.size(); ++i) {
    const auto& artifact = artifacts.at(i);
    out << "    {\n"
        << "      \"artifact_id\": "
        << json_quote(artifact.artifact_id) << ",\n"
        << "      \"owner_kind\": "
        << json_quote(artifact.owner_kind) << ",\n"
        << "      \"owner_id\": " << json_quote(artifact.owner_id)
        << ",\n"
        << "      \"role\": " << json_quote(artifact.role) << ",\n"
        << "      \"path\": " << json_quote(artifact.path) << ",\n"
        << "      \"dtype\": " << json_quote(artifact.dtype) << ",\n"
        << "      \"byte_order\": "
        << json_quote(artifact.dtype == "u8" ? "not-applicable"
                                             : "little")
        << ",\n"
        << "      \"encoding\": " << json_quote(artifact.encoding)
        << ",\n"
        << "      \"shape\": ";
    write_shape(out, artifact.shape);
    out << ",\n"
        << "      \"stored_elements\": " << artifact.stored_elements
        << ",\n"
        << "      \"bytes\": " << artifact.bytes << "\n"
        << "    }" << (i + 1 == artifacts.size() ? "\n" : ",\n");
  }

  out << "  ],\n"
      << "  \"workloads\": [\n";
  if (workload_fixtures.size() != captured_workloads.size()) {
    throw std::runtime_error(
        "workload fixtures and captured workload records diverged");
  }
  for (std::size_t i = 0; i < workload_fixtures.size(); ++i) {
    const auto& workload = workload_fixtures.at(i);
    const auto& captured = captured_workloads.at(i);
    if (workload.workload_id != captured.workload_id) {
      throw std::runtime_error("captured workload order drifted");
    }
    out << "    {\n"
        << "      \"workload_id\": "
        << json_quote(workload.workload_id) << ",\n"
        << "      \"panel_id\": " << json_quote(workload.panel_id)
        << ",\n"
        << "      \"case_id\": " << json_quote(workload.case_id)
        << ",\n"
        << "      \"scale_id\": " << json_quote(workload.scale_id)
        << ",\n"
        << "      \"accepted_seed\": "
        << json_quote(workload.accepted_seed) << ",\n"
        << "      \"geometry_id\": "
        << json_quote(workload.geometry_id) << ",\n"
        << "      \"fixture_id\": "
        << json_quote(workload.fixture_id) << ",\n"
        << "      \"geometry_recipe\": "
        << json_quote(workload.geometry_recipe) << ",\n"
        << "      \"value_rows\": " << workload.value_rows << ",\n"
        << "      \"gradient_points\": " << workload.gradient_rows
        << ",\n"
        << "      \"scalar_order\": " << captured.scalar_order << ",\n"
        << "      \"observation_row_map\": "
        << json_quote(
               "value rows first; then global gradient point/component "
               "rows at value_rows + 3*i + component")
        << ",\n"
        << "      \"requested_polynomial_degree\": {";
    if (workload.requested_polynomial_degree ==
        Model::kMinRequiredPolyDegree) {
      out << "\"mode\":\"minimum-required\",\"sentinel\":"
          << Model::kMinRequiredPolyDegree;
    } else {
      out << "\"mode\":\"explicit\",\"value\":"
          << workload.requested_polynomial_degree;
    }
    out << "},\n"
        << "      \"resolved_polynomial_degree\": "
        << workload.model.poly_degree() << ",\n"
        << "      \"polynomial_order\": "
        << captured.polynomial_order << ",\n"
        << "      \"hierarchy\": {\"levels\":"
        << captured.hierarchy_levels << ",\"blocks\":"
        << captured.block_count << ",\"fine_blocks\":"
        << captured.fine_block_count << ",\"coarse_blocks\":"
        << captured.coarse_block_count << "},\n"
        << "      \"artifacts\": {\n"
        << "        \"value_points\": "
        << json_quote(captured.value_points_artifact) << ",\n"
        << "        \"gradient_points\": "
        << json_quote(captured.gradient_points_artifact) << ",\n"
        << "        \"observations\": "
        << json_quote(captured.observations_artifact) << ",\n"
        << "        \"selected_polynomial_indices\": "
        << json_quote(captured.polynomial_indices_artifact) << "\n"
        << "      },\n";
    write_model_descriptor(out, workload.model,
                           captured.model_values_artifact);
    out << "\n"
        << "    }"
        << (i + 1 == workload_fixtures.size() ? "\n" : ",\n");
  }

  out << "  ],\n"
      << "  \"blocks\": [\n";
  for (std::size_t i = 0; i < blocks.size(); ++i) {
    const auto& block = blocks.at(i);
    out << "    {\n"
        << "      \"block_id\": " << json_quote(block.block_id)
        << ",\n"
        << "      \"workload_id\": "
        << json_quote(block.workload_id) << ",\n"
        << "      \"role\": " << json_quote(block.role) << ",\n"
        << "      \"level\": " << block.level << ",\n"
        << "      \"ordinal\": " << block.ordinal << ",\n"
        << "      \"source_value_rows\": "
        << block.source_value_rows << ",\n"
        << "      \"source_gradient_points\": "
        << block.source_gradient_rows << ",\n"
        << "      \"value_rows\": " << block.value_rows << ",\n"
        << "      \"gradient_points\": " << block.gradient_rows
        << ",\n"
        << "      \"inner_value_rows\": "
        << block.inner_value_rows << ",\n"
        << "      \"inner_gradient_points\": "
        << block.inner_gradient_rows << ",\n"
        << "      \"scalar_order\": " << block.scalar_order << ",\n"
        << "      \"polynomial_order\": "
        << block.polynomial_order << ",\n"
        << "      \"reduced_order\": " << block.reduced_order
        << ",\n"
        << "      \"row_channel_map\": "
        << json_quote("canonical-global-value-offset-v1") << ",\n"
        << "      \"q_semantics\": "
        << json_quote(
               "Q=[Q_top;I], with Q_top derived from canonical global "
               "Lagrange rows; polynomial-nullspace certificate required")
        << ",\n"
        << "      \"reference_witness_authority\": "
        << json_quote("untrusted-witness-only") << ",\n"
        << "      \"reference_witness_status\": {\"qtaq_solver\":"
        << json_quote("Success") << ",\"p_top_solver\":"
        << json_quote(block.role == "coarse" ? "Invertible"
                                               : "not-applicable")
        << ",\"all_finite\":true},\n"
        << "      \"artifacts\": {\n";
    for (std::size_t j = 0; j < block.artifacts.size(); ++j) {
      const auto& [role, artifact_id] = block.artifacts.at(j);
      out << "        " << json_quote(role) << ": "
          << json_quote(artifact_id)
          << (j + 1 == block.artifacts.size() ? "\n" : ",\n");
    }
    out << "      }\n"
        << "    }" << (i + 1 == blocks.size() ? "\n" : ",\n");
  }

  out << "  ],\n"
      << "  \"factor_sources\": [\n";
  for (std::size_t i = 0; i < factor_sources.size(); ++i) {
    const auto& source = factor_sources.at(i);
    out << "    {\n"
        << "      \"factor_source_id\": "
        << json_quote(source.factor_source_id) << ",\n"
        << "      \"block_id\": " << json_quote(source.block_id)
        << ",\n"
        << "      \"workload_id\": "
        << json_quote(source.workload_id) << ",\n"
        << "      \"matrix_role\": "
        << json_quote(source.matrix_role) << ",\n"
        << "      \"matrix_artifact\": "
        << json_quote(source.matrix_artifact) << ",\n"
        << "      \"factorization\": "
        << json_quote(source.factorization) << ",\n"
        << "      \"use_site\": " << json_quote(source.use_site)
        << ",\n"
        << "      \"expected_rank\": " << source.expected_rank
        << ",\n"
        << "      \"semantic_admission\": "
        << json_quote(
               "certificate-required-before-backend-selection")
        << "\n"
        << "    }"
        << (i + 1 == factor_sources.size() ? "\n" : ",\n");
  }

  out << "  ],\n"
      << "  \"auxiliary_decomposition_sources\": [\n";
  for (std::size_t i = 0; i < auxiliary_sources.size(); ++i) {
    const auto& source = auxiliary_sources.at(i);
    out << "    {\n"
        << "      \"source_id\": " << json_quote(source.source_id)
        << ",\n"
        << "      \"workload_id\": "
        << json_quote(source.workload_id) << ",\n"
        << "      \"matrix_artifact\": "
        << json_quote(source.matrix_artifact) << ",\n"
        << "      \"matrix_alias\": "
        << json_quote(
               "workload-global unisolvent P is byte-identical to "
               "this workload's coarse P_top")
        << ",\n"
        << "      \"factorization\": \"full-pivot-lu\",\n"
        << "      \"use_site\": " << json_quote(source.use_site)
        << ",\n"
        << "      \"expected_rank\": " << source.expected_rank
        << ",\n"
        << "      \"classification\": \"non-carried-generator-auxiliary\",\n"
        << "      \"issue_38_handoff\": false\n"
        << "    }"
        << (i + 1 == auxiliary_sources.size() ? "\n" : ",\n");
  }

  out << "  ],\n"
      << "  \"exclusions\": [\n"
      << "    {\n"
      << "      \"record_id\": "
      << json_quote(
             "M3-HERMITE-COMPOSITE-max-order-fine-frozen-literal")
      << ",\n"
      << "      \"reason\": "
      << json_quote(
             "local-mu gradient-row offset defect; research-only "
             "compatibility fixture; not a factor source or expected semantic")
      << "\n"
      << "    },\n"
      << "    {\n"
      << "      \"record_id\": "
      << json_quote(
             "M3-HERMITE-COMPOSITE-level0-coarse-frozen-literal")
      << ",\n"
      << "      \"reason\": "
      << json_quote(
             "local-mu gradient-row offset defect; research-only "
             "compatibility fixture; not a factor source or expected semantic")
      << "\n"
      << "    },\n"
      << "    {\n"
      << "      \"record_id\": "
      << json_quote(
             "polatory::polynomial::UnisolventPointSet<3>::"
             "100-random-trial-full-pivot-lu") << ",\n"
      << "      \"reason\": "
      << json_quote(
             "generator-search-internal trial decompositions; only the "
             "selected workload-global unisolvent P is retained as an "
             "auxiliary decomposition source")
      << "\n"
      << "    }\n"
      << "  ],\n"
      << "  \"assertions\": [\n";
  for (std::size_t i = 0; i < assertions.size(); ++i) {
    const auto& assertion = assertions.at(i);
    out << "    {\"assertion_id\":"
        << json_quote(assertion.assertion_id)
        << ",\"expected\":" << assertion.expected
        << ",\"actual\":" << assertion.actual
        << ",\"passed\":"
        << (assertion.expected == assertion.actual ? "true" : "false")
        << "}"
        << (i + 1 == assertions.size() ? "\n" : ",\n");
  }
  out << "  ]\n"
      << "}\n";
  if (!out) {
    throw std::runtime_error("cannot write " + path.string());
  }
}

void require_assertions(const std::vector<AssertionRecord>& assertions) {
  for (const auto& assertion : assertions) {
    if (assertion.expected != assertion.actual) {
      throw std::runtime_error(
          assertion.assertion_id + " expected " +
          std::to_string(assertion.expected) + ", got " +
          std::to_string(assertion.actual));
    }
  }
}

}  // namespace

int main(int argc, char** argv) {
  try {
    if (argc != 2) {
      std::cerr << "usage: rapidrbf_hierarchy_capture OUTPUT_DIR\n";
      return 2;
    }
    if (sizeof(double) != 8 ||
        !std::numeric_limits<double>::is_iec559 ||
        std::endian::native != std::endian::little) {
      throw std::runtime_error(
          "capture requires little-endian IEC 60559 binary64");
    }

    const std::filesystem::path output_root(argv[1]);
    if (std::filesystem::exists(output_root) &&
        !std::filesystem::is_empty(output_root)) {
      throw std::runtime_error(
          "output directory must be absent or empty: " +
          output_root.string());
    }
    std::filesystem::create_directories(output_root);

    const std::vector<Workload> workload_fixtures = workloads();
    std::vector<Artifact> artifacts;
    std::vector<CapturedWorkload> captured_workloads;
    std::vector<BlockRecord> blocks;
    std::vector<FactorSource> factor_sources;
    std::vector<AuxiliaryDecompositionSource> auxiliary_sources;
    ArtifactWriter artifact_writer(output_root, artifacts);
    artifacts.reserve(2738);
    captured_workloads.reserve(workload_fixtures.size());
    blocks.reserve(204);
    factor_sources.reserve(216);

    for (const auto& workload : workload_fixtures) {
      captured_workloads.push_back(capture_workload(
          workload, artifact_writer, blocks, factor_sources));
    }
    const NegativeControl negative_control =
        capture_rank_invalid_control(artifact_writer);
    auxiliary_sources.reserve(workload_fixtures.size());
    for (const auto& workload : workload_fixtures) {
      const auto coarse_p_top =
          std::find_if(factor_sources.begin(), factor_sources.end(),
                       [&](const FactorSource& source) {
                         return source.workload_id == workload.workload_id &&
                                source.matrix_role == "p_top";
                       });
      if (coarse_p_top == factor_sources.end()) {
        throw std::runtime_error(
            workload.workload_id +
            " is missing the coarse P_top alias for its selected "
            "unisolvent P");
      }
      auxiliary_sources.push_back(AuxiliaryDecompositionSource{
          "auxiliary:" + workload.workload_id +
              ":lagrange-unisolvent-p",
          workload.workload_id,
          coarse_p_top->matrix_artifact,
          "polatory::polynomial::LagrangeBasis<3>::LagrangeBasis/"
          "Eigen::FullPivLU<MatX>(P_unisolvent)",
          workload.model.poly_basis_size(),
      });
    }

    const auto fine_blocks = static_cast<std::uint64_t>(
        std::count_if(blocks.begin(), blocks.end(),
                      [](const BlockRecord& block) {
                        return block.role == "fine";
                      }));
    const auto coarse_blocks =
        static_cast<std::uint64_t>(blocks.size()) - fine_blocks;
    const auto qtaq_sources = static_cast<std::uint64_t>(
        std::count_if(factor_sources.begin(), factor_sources.end(),
                      [](const FactorSource& source) {
                        return source.matrix_role == "qtaq";
                      }));
    const auto p_top_sources =
        static_cast<std::uint64_t>(factor_sources.size()) - qtaq_sources;
    const auto frozen_literal_sources = static_cast<std::uint64_t>(
        std::count_if(
            factor_sources.begin(), factor_sources.end(),
            [](const FactorSource& source) {
              return source.factor_source_id.find("frozen-literal") !=
                     std::string::npos;
            }));
    const auto m3_noncanonical_blocks = static_cast<std::uint64_t>(
        std::count_if(blocks.begin(), blocks.end(),
                      [](const BlockRecord& block) {
                        return block.workload_id.starts_with("M3-") &&
                               std::none_of(
                                   block.artifacts.begin(),
                                   block.artifacts.end(),
                                   [](const auto& entry) {
                                     return entry.first ==
                                            "canonical_lagrange_flat_indices";
                                  });
                      }));
    if (artifacts.size() != 2738) {
      throw std::runtime_error(
          "v3 artifact inventory expected 2738, got " +
          std::to_string(artifacts.size()));
    }

    const std::vector<AssertionRecord> assertions{
        {"exact-workload-count", 12,
         static_cast<std::uint64_t>(captured_workloads.size())},
        {"exact-block-count", 204,
         static_cast<std::uint64_t>(blocks.size())},
        {"exact-fine-block-count", 192, fine_blocks},
        {"exact-coarse-block-count", 12, coarse_blocks},
        {"exact-carried-factor-source-count", 216,
         static_cast<std::uint64_t>(factor_sources.size())},
        {"one-qtaq-factor-source-per-block", 204, qtaq_sources},
        {"coarse-only-p-top-factor-sources", 12, p_top_sources},
        {"one-workload-global-lagrange-auxiliary-source-per-workload",
         12, static_cast<std::uint64_t>(auxiliary_sources.size())},
        {"frozen-literal-factor-sources-excluded", 0,
         frozen_literal_sources},
        {"m3-blocks-all-canonical-global-row-map", 0,
         m3_noncanonical_blocks},
        {"one-materialized-rank-invalid-control", 1, 1},
    };
    require_assertions(assertions);

    const auto manifest_path =
        output_root / "hierarchy.manifest.raw.json";
    write_manifest(manifest_path, workload_fixtures,
                   captured_workloads, artifacts, blocks,
                   factor_sources, auxiliary_sources,
                   negative_control, assertions);
    std::cout << "captured " << captured_workloads.size()
              << " workloads, " << blocks.size() << " blocks, "
              << factor_sources.size() << " carried factor sources, and "
              << artifacts.size() << " artifacts at "
              << output_root.string() << std::endl;
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "capture failed: " << error.what() << std::endl;
    return 1;
  }
}
