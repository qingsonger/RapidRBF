#include <Eigen/Core>

#include <bit>
#include <cmath>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <limits>
#include <locale>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#include <polatory/interpolation/direct_operator.hpp>
#include <polatory/model.hpp>
#include <polatory/polynomial/monomial_basis.hpp>
#include <polatory/rbf/make_rbf.hpp>

namespace {

using polatory::Index;
using polatory::MatX;
using polatory::VecX;

constexpr std::string_view kSchema = "polatory-frozen-source-diagnostic-v1";
constexpr std::string_view kEvidence = "instrumented_diagnostic_evidence";

std::size_t g_record_count = 0;

std::string json_quote(std::string_view text) {
  std::ostringstream out;
  out << '"';
  for (unsigned char c : text) {
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

std::string fp_class(double value) {
  switch (std::fpclassify(value)) {
    case FP_INFINITE:
      return std::signbit(value) ? "negative_infinity" : "positive_infinity";
    case FP_NAN:
      return "nan";
    case FP_ZERO:
      return std::signbit(value) ? "negative_zero" : "positive_zero";
    case FP_SUBNORMAL:
      return "subnormal";
    case FP_NORMAL:
      return "normal";
    default:
      return "unknown";
  }
}

std::string json_double(double value) {
  static_assert(sizeof(double) == sizeof(std::uint64_t));
  const auto bits = std::bit_cast<std::uint64_t>(value);

  std::ostringstream out;
  out << "{\"hex\":\"0x" << std::hex << std::setw(16) << std::setfill('0') << bits
      << "\",\"class\":" << json_quote(fp_class(value)) << '}';
  return out.str();
}

std::string json_double_vector(const std::vector<double>& values) {
  std::ostringstream out;
  out << '[';
  for (std::size_t i = 0; i < values.size(); ++i) {
    if (i != 0) {
      out << ',';
    }
    out << json_double(values[i]);
  }
  out << ']';
  return out.str();
}

std::string json_string_vector(const std::vector<std::string>& values) {
  std::ostringstream out;
  out << '[';
  for (std::size_t i = 0; i < values.size(); ++i) {
    if (i != 0) {
      out << ',';
    }
    out << json_quote(values[i]);
  }
  out << ']';
  return out.str();
}

template <class Derived>
std::string json_matrix(const Eigen::MatrixBase<Derived>& matrix) {
  std::ostringstream out;
  out << '[';
  for (Index row = 0; row < matrix.rows(); ++row) {
    if (row != 0) {
      out << ',';
    }
    out << '[';
    for (Index column = 0; column < matrix.cols(); ++column) {
      if (column != 0) {
        out << ',';
      }
      out << json_double(matrix(row, column));
    }
    out << ']';
  }
  out << ']';
  return out.str();
}

std::string exception_json(std::string_view type, std::string_view what) {
  return "{\"outcome\":\"threw\",\"exception_type\":" + json_quote(type) +
         ",\"what\":" + json_quote(what) + '}';
}

template <class Function>
std::string observe_void(Function&& function) {
  try {
    std::forward<Function>(function)();
    return "{\"outcome\":\"returned\"}";
  } catch (const std::invalid_argument& error) {
    return exception_json("std::invalid_argument", error.what());
  } catch (const std::runtime_error& error) {
    return exception_json("std::runtime_error", error.what());
  } catch (const std::exception& error) {
    return exception_json("std::exception", error.what());
  } catch (...) {
    return exception_json("unknown", "");
  }
}

template <class Function>
std::string observe_scalar(Function&& function) {
  try {
    return "{\"outcome\":\"returned\",\"value\":" +
           json_double(std::forward<Function>(function)()) + '}';
  } catch (const std::invalid_argument& error) {
    return exception_json("std::invalid_argument", error.what());
  } catch (const std::runtime_error& error) {
    return exception_json("std::runtime_error", error.what());
  } catch (const std::exception& error) {
    return exception_json("std::exception", error.what());
  } catch (...) {
    return exception_json("unknown", "");
  }
}

template <class Function>
std::string observe_matrix(Function&& function) {
  try {
    const auto result = std::forward<Function>(function)();
    return "{\"outcome\":\"returned\",\"value\":" + json_matrix(result) + '}';
  } catch (const std::invalid_argument& error) {
    return exception_json("std::invalid_argument", error.what());
  } catch (const std::runtime_error& error) {
    return exception_json("std::runtime_error", error.what());
  } catch (const std::exception& error) {
    return exception_json("std::exception", error.what());
  } catch (...) {
    return exception_json("unknown", "");
  }
}

void emit(std::string_view kind, const std::string& fields = {}) {
  std::cout << "{\"schema\":" << json_quote(kSchema) << ",\"evidence\":" << json_quote(kEvidence)
            << ",\"kind\":" << json_quote(kind) << fields << "}\n";
  ++g_record_count;
}

std::vector<std::string> family_names() {
  return {"bh2", "bh3", "cub", "exp", "gau", "gc3", "gc5", "gc7",
          "gc9", "sph", "sp3", "sp5", "sp7", "sp9", "th2", "th3"};
}

bool is_polyharmonic(std::string_view name) {
  return name == "bh2" || name == "bh3" || name == "th2" || name == "th3";
}

std::vector<double> ordinary_parameters(std::string_view name) {
  if (is_polyharmonic(name)) {
    return {1.25, 0.0};
  }
  return {1.25, 1.0};
}

double spheroidal_branch(std::string_view name) {
  if (name == "sp3") {
    return 0.18657871684006438;
  }
  if (name == "sp5") {
    return 0.2580127411803573;
  }
  if (name == "sp7") {
    return 0.2944149476843637;
  }
  if (name == "sp9") {
    return 0.31622776601683794;
  }
  throw std::invalid_argument("not a spheroidal family");
}

template <int Dim>
using Rbf = polatory::rbf::Rbf<Dim>;

template <int Dim>
using Vector = polatory::geometry::Vector<Dim>;

template <int Dim>
using Points = polatory::geometry::Points<Dim>;

template <int Dim>
Vector<Dim> radial_point(double radius) {
  Vector<Dim> point = Vector<Dim>::Zero();
  point(0) = radius;
  return point;
}

template <int Dim>
Vector<Dim> regular_point() {
  constexpr double coordinates[] = {0.125, -0.25, 0.375};
  Vector<Dim> point;
  for (int column = 0; column < Dim; ++column) {
    point(column) = coordinates[column];
  }
  return point;
}

template <int Dim>
void emit_rbf_metadata(const Rbf<Dim>& rbf) {
  std::ostringstream fields;
  fields << ",\"dimension\":" << Dim << ",\"family\":" << json_quote(rbf.short_name())
         << ",\"cpd_order\":" << rbf.cpd_order()
         << ",\"is_covariance\":" << (rbf.is_covariance_function() ? "true" : "false")
         << ",\"num_parameters\":" << rbf.num_parameters()
         << ",\"parameter_names\":" << json_string_vector(rbf.parameter_names())
         << ",\"parameters\":" << json_double_vector(rbf.parameters())
         << ",\"parameter_lower_bounds\":" << json_double_vector(rbf.parameter_lower_bounds())
         << ",\"parameter_upper_bounds\":" << json_double_vector(rbf.parameter_upper_bounds())
         << ",\"support_radius_isotropic\":" << json_double(rbf.support_radius_isotropic())
         << ",\"anisotropy\":" << json_matrix(rbf.anisotropy());
  emit("rbf_metadata", fields.str());
}

template <int Dim>
void emit_rbf_evaluation(const Rbf<Dim>& rbf, std::string_view point_class,
                         const Vector<Dim>& difference) {
  std::ostringstream fields;
  fields << ",\"dimension\":" << Dim << ",\"family\":" << json_quote(rbf.short_name())
         << ",\"point_class\":" << json_quote(point_class)
         << ",\"difference\":" << json_matrix(difference)
         << ",\"value\":" << observe_scalar([&] { return rbf.evaluate(difference); })
         << ",\"gradient\":" << observe_matrix([&] { return rbf.evaluate_gradient(difference); })
         << ",\"hessian\":" << observe_matrix([&] { return rbf.evaluate_hessian(difference); });
  emit("rbf_evaluation", fields.str());
}

template <int Dim>
void probe_rbf_family(std::string_view name) {
  auto rbf = polatory::rbf::make_rbf<Dim>(std::string(name), ordinary_parameters(name));
  emit_rbf_metadata(rbf);

  const Vector<Dim> origin = Vector<Dim>::Zero();
  emit_rbf_evaluation(rbf, "origin", origin);
  emit_rbf_evaluation(rbf, "near_zero", radial_point<Dim>(std::ldexp(1.0, -500)));
  emit_rbf_evaluation(rbf, "regular", regular_point<Dim>());

  if (name == "cub" || name == "sph") {
    constexpr double boundary = 1.0;
    emit_rbf_evaluation(rbf, "support_nextafter_inside",
                        radial_point<Dim>(std::nextafter(boundary, 0.0)));
    emit_rbf_evaluation(rbf, "support_exact", radial_point<Dim>(boundary));
    emit_rbf_evaluation(rbf, "support_nextafter_outside",
                        radial_point<Dim>(
                            std::nextafter(boundary, std::numeric_limits<double>::infinity())));
  }

  if (name == "sp3" || name == "sp5" || name == "sp7" || name == "sp9") {
    const double boundary = spheroidal_branch(name);
    emit_rbf_evaluation(rbf, "spheroidal_nextafter_below",
                        radial_point<Dim>(std::nextafter(boundary, 0.0)));
    emit_rbf_evaluation(rbf, "spheroidal_exact", radial_point<Dim>(boundary));
    emit_rbf_evaluation(
        rbf, "spheroidal_nextafter_above",
        radial_point<Dim>(
            std::nextafter(boundary, std::numeric_limits<double>::infinity())));
  }
}

template <int Dim>
void probe_all_rbf_families() {
  for (const auto& name : family_names()) {
    probe_rbf_family<Dim>(name);
  }
}

template <int Dim>
void emit_rbf_construction(std::string_view observation, std::string_view family,
                           const std::vector<double>& parameters) {
  std::ostringstream fields;
  fields << ",\"dimension\":" << Dim << ",\"observation\":" << json_quote(observation)
         << ",\"requested_family\":" << json_quote(family)
         << ",\"requested_parameters\":" << json_double_vector(parameters);
  try {
    auto rbf = polatory::rbf::make_rbf<Dim>(std::string(family), parameters);
    fields << ",\"outcome\":\"returned\",\"stored_family\":" << json_quote(rbf.short_name())
           << ",\"stored_parameters\":" << json_double_vector(rbf.parameters());
  } catch (const std::invalid_argument& error) {
    fields << ",\"outcome\":\"threw\",\"exception_type\":\"std::invalid_argument\",\"what\":"
           << json_quote(error.what());
  } catch (const std::runtime_error& error) {
    fields << ",\"outcome\":\"threw\",\"exception_type\":\"std::runtime_error\",\"what\":"
           << json_quote(error.what());
  } catch (const std::exception& error) {
    fields << ",\"outcome\":\"threw\",\"exception_type\":\"std::exception\",\"what\":"
           << json_quote(error.what());
  }
  emit("rbf_construction_observation", fields.str());
}

void probe_rbf_parameter_behavior() {
  emit_rbf_construction<1>("polyharmonic_empty_defaults", "bh2", {});
  emit_rbf_construction<1>("polyharmonic_one_parameter_defaults_c", "bh2", {2.0});
  emit_rbf_construction<1>("polyharmonic_three_parameters", "bh2", {1.0, 2.0, 3.0});
  emit_rbf_construction<1>("covariance_one_parameter", "gau", {1.0});
  emit_rbf_construction<1>("covariance_three_parameters", "gau", {1.0, 2.0, 3.0});
  emit_rbf_construction<1>("negative_covariance_parameters", "gau", {-1.0, -2.0});
  emit_rbf_construction<1>("zero_covariance_range", "gau", {1.0, 0.0});
  emit_rbf_construction<1>("nan_psill", "gau",
                           {std::numeric_limits<double>::quiet_NaN(), 1.0});
  emit_rbf_construction<1>("infinite_range", "gau",
                           {1.0, std::numeric_limits<double>::infinity()});
  emit_rbf_construction<1>("unknown_family", "not-an-rbf", {1.0, 1.0});
}

template <int Dim>
Eigen::Matrix<double, Dim, Dim, Eigen::RowMajor> diagonal_matrix(
    const std::vector<double>& diagonal) {
  Eigen::Matrix<double, Dim, Dim, Eigen::RowMajor> matrix =
      Eigen::Matrix<double, Dim, Dim, Eigen::RowMajor>::Zero();
  for (int i = 0; i < Dim; ++i) {
    matrix(i, i) = diagonal.at(static_cast<std::size_t>(i));
  }
  return matrix;
}

template <int Dim>
void emit_anisotropy_observation(
    std::string_view observation,
    const Eigen::Matrix<double, Dim, Dim, Eigen::RowMajor>& candidate) {
  auto rbf = polatory::rbf::make_rbf<Dim>("gau", {1.25, 1.0});
  const double determinant = candidate.determinant();

  bool accepted = false;
  const auto outcome = observe_void([&] {
    rbf.set_anisotropy(candidate);
    accepted = true;
  });

  std::ostringstream fields;
  fields << ",\"dimension\":" << Dim << ",\"family\":\"gau\",\"observation\":"
         << json_quote(observation) << ",\"candidate\":" << json_matrix(candidate)
         << ",\"candidate_determinant\":" << json_double(determinant)
         << ",\"accepted\":" << (accepted ? "true" : "false") << ",\"operation\":" << outcome
         << ",\"stored_anisotropy_after_operation\":" << json_matrix(rbf.anisotropy());
  if (accepted) {
    const auto difference = regular_point<Dim>();
    fields << ",\"difference\":" << json_matrix(difference)
           << ",\"value\":" << observe_scalar([&] { return rbf.evaluate(difference); })
           << ",\"gradient\":"
           << observe_matrix([&] { return rbf.evaluate_gradient(difference); })
           << ",\"hessian\":"
           << observe_matrix([&] { return rbf.evaluate_hessian(difference); });
  }
  emit("anisotropy_observation", fields.str());
}

template <int Dim>
void probe_anisotropy() {
  using Matrix = Eigen::Matrix<double, Dim, Dim, Eigen::RowMajor>;

  emit_anisotropy_observation<Dim>("identity", Matrix::Identity());

  std::vector<double> diagonal(static_cast<std::size_t>(Dim));
  constexpr double diagonal_values[] = {2.0, 0.5, 4.0};
  for (int i = 0; i < Dim; ++i) {
    diagonal[static_cast<std::size_t>(i)] = diagonal_values[i];
  }
  emit_anisotropy_observation<Dim>("positive_diagonal", diagonal_matrix<Dim>(diagonal));

  if constexpr (Dim >= 2) {
    Matrix shear = Matrix::Identity();
    shear(0, 1) = 0.5;
    if constexpr (Dim == 3) {
      shear(1, 2) = -0.25;
      shear(0, 2) = 0.125;
    }
    emit_anisotropy_observation<Dim>("shear", shear);
  }

  std::vector<double> ill_conditioned(static_cast<std::size_t>(Dim), 1.0);
  ill_conditioned.front() = std::ldexp(1.0, -500);
  if constexpr (Dim >= 2) {
    ill_conditioned.back() = std::ldexp(1.0, 500);
  }
  emit_anisotropy_observation<Dim>("ill_conditioned_positive_determinant",
                                   diagonal_matrix<Dim>(ill_conditioned));

  std::vector<double> singular(static_cast<std::size_t>(Dim), 1.0);
  singular.back() = 0.0;
  emit_anisotropy_observation<Dim>("singular", diagonal_matrix<Dim>(singular));

  std::vector<double> reflection(static_cast<std::size_t>(Dim), 1.0);
  reflection.front() = -1.0;
  emit_anisotropy_observation<Dim>("reflection", diagonal_matrix<Dim>(reflection));

  std::vector<double> nan_matrix(static_cast<std::size_t>(Dim), 1.0);
  nan_matrix.front() = std::numeric_limits<double>::quiet_NaN();
  emit_anisotropy_observation<Dim>("nonfinite_nan", diagonal_matrix<Dim>(nan_matrix));

  std::vector<double> positive_infinity(static_cast<std::size_t>(Dim), 1.0);
  positive_infinity.front() = std::numeric_limits<double>::infinity();
  emit_anisotropy_observation<Dim>("nonfinite_positive_infinity",
                                   diagonal_matrix<Dim>(positive_infinity));

  std::vector<double> negative_infinity(static_cast<std::size_t>(Dim), 1.0);
  negative_infinity.front() = -std::numeric_limits<double>::infinity();
  emit_anisotropy_observation<Dim>("nonfinite_negative_infinity",
                                   diagonal_matrix<Dim>(negative_infinity));
}

template <int Dim>
std::string model_state_json(const polatory::Model<Dim>& model) {
  std::vector<std::string> rbf_names;
  rbf_names.reserve(static_cast<std::size_t>(model.num_rbfs()));
  for (const auto& rbf : model.rbfs()) {
    rbf_names.push_back(rbf.short_name());
  }

  std::ostringstream out;
  out << "{\"cpd_order\":" << model.cpd_order() << ",\"poly_degree\":" << model.poly_degree()
      << ",\"poly_basis_size\":" << model.poly_basis_size()
      << ",\"is_covariance_model\":" << (model.is_covariance_model() ? "true" : "false")
      << ",\"nugget\":" << json_double(model.nugget())
      << ",\"num_rbfs\":" << model.num_rbfs()
      << ",\"rbf_order\":" << json_string_vector(rbf_names)
      << ",\"num_parameters\":" << model.num_parameters()
      << ",\"parameter_names\":" << json_string_vector(model.parameter_names())
      << ",\"parameters\":" << json_double_vector(model.parameters())
      << ",\"parameter_lower_bounds\":" << json_double_vector(model.parameter_lower_bounds())
      << ",\"parameter_upper_bounds\":" << json_double_vector(model.parameter_upper_bounds())
      << '}';
  return out.str();
}

template <int Dim>
void emit_model_snapshot(std::string_view observation, const polatory::Model<Dim>& model) {
  std::ostringstream fields;
  fields << ",\"dimension\":" << Dim << ",\"observation\":" << json_quote(observation)
         << ",\"state\":" << model_state_json(model);
  emit("model_observation", fields.str());
}

template <int Dim>
void emit_model_construction_error(std::string_view observation, std::string outcome) {
  std::ostringstream fields;
  fields << ",\"dimension\":" << Dim << ",\"observation\":" << json_quote(observation)
         << ",\"operation\":" << outcome;
  emit("model_error_observation", fields.str());
}

template <int Dim, class Function>
void emit_model_mutation(std::string_view observation, polatory::Model<Dim> model,
                         Function&& mutation) {
  const auto before = model_state_json(model);
  const auto outcome = observe_void([&] { std::forward<Function>(mutation)(model); });
  const auto after = model_state_json(model);

  std::ostringstream fields;
  fields << ",\"dimension\":" << Dim << ",\"observation\":" << json_quote(observation)
         << ",\"state_before\":" << before << ",\"operation\":" << outcome
         << ",\"state_after\":" << after;
  emit("model_mutation_observation", fields.str());
}

template <int Dim>
polatory::Model<Dim> gaussian_model() {
  return polatory::Model<Dim>(polatory::rbf::make_rbf<Dim>("gau", {1.25, 1.0}));
}

template <int Dim>
void probe_models() {
  for (const auto& name : family_names()) {
    auto model =
        polatory::Model<Dim>(polatory::rbf::make_rbf<Dim>(name, ordinary_parameters(name)));
    emit_model_snapshot("automatic_degree_" + name, model);
  }

  for (int degree = -1; degree <= 2; ++degree) {
    auto model =
        polatory::Model<Dim>(polatory::rbf::make_rbf<Dim>("gau", {1.25, 1.0}), degree);
    emit_model_snapshot("explicit_covariance_degree_" + std::to_string(degree), model);
  }

  std::vector<Rbf<Dim>> components;
  components.push_back(polatory::rbf::make_rbf<Dim>("gau", {1.25, 1.0}));
  components.push_back(polatory::rbf::make_rbf<Dim>("th2", {2.0, 0.0}));
  polatory::Model<Dim> composite(std::move(components));
  emit_model_snapshot("composite_automatic_degree_before_parameters", composite);
  composite.set_parameters({0.125, 2.0, 3.0, 4.0, 0.25});
  emit_model_snapshot("composite_after_ordered_parameters", composite);

  emit_model_construction_error<Dim>(
      "empty_rbf_vector",
      observe_void([] {
        std::vector<Rbf<Dim>> empty;
        polatory::Model<Dim> model(std::move(empty));
        (void)model;
      }));
  emit_model_construction_error<Dim>(
      "degree_below_minimum",
      observe_void([] {
        polatory::Model<Dim> model(
            polatory::rbf::make_rbf<Dim>("gau", {1.25, 1.0}), -3);
        (void)model;
      }));
  emit_model_construction_error<Dim>(
      "degree_above_maximum",
      observe_void([] {
        polatory::Model<Dim> model(
            polatory::rbf::make_rbf<Dim>("gau", {1.25, 1.0}), 3);
        (void)model;
      }));
  emit_model_construction_error<Dim>(
      "degree_below_component_cpd_minimum",
      observe_void([] {
        polatory::Model<Dim> model(
            polatory::rbf::make_rbf<Dim>("th2", {1.25, 0.0}), 1);
        (void)model;
      }));

  auto noncovariance =
      polatory::Model<Dim>(polatory::rbf::make_rbf<Dim>("th3", {1.25, 0.0}));
  std::ostringstream description_fields;
  description_fields << ",\"dimension\":" << Dim
                     << ",\"observation\":\"description_of_non_covariance_model\""
                     << ",\"operation\":"
                     << observe_void([&] { (void)noncovariance.description(); });
  emit("model_error_observation", description_fields.str());

  emit_model_mutation("negative_nugget", gaussian_model<Dim>(),
                      [](auto& model) { model.set_nugget(-1.0); });
  emit_model_mutation(
      "nan_nugget", gaussian_model<Dim>(),
      [](auto& model) { model.set_nugget(std::numeric_limits<double>::quiet_NaN()); });
  emit_model_mutation(
      "positive_infinite_nugget", gaussian_model<Dim>(),
      [](auto& model) { model.set_nugget(std::numeric_limits<double>::infinity()); });
  emit_model_mutation("too_few_model_parameters", gaussian_model<Dim>(),
                      [](auto& model) { model.set_parameters({0.0, 1.0}); });
  emit_model_mutation("too_many_model_parameters", gaussian_model<Dim>(),
                      [](auto& model) { model.set_parameters({0.0, 1.0, 2.0, 3.0}); });
  emit_model_mutation("negative_nugget_via_parameters", gaussian_model<Dim>(),
                      [](auto& model) { model.set_parameters({-1.0, 2.0, 3.0}); });
  emit_model_mutation("negative_rbf_parameters", gaussian_model<Dim>(),
                      [](auto& model) { model.set_parameters({0.125, -2.0, -3.0}); });
  emit_model_mutation(
      "nonfinite_rbf_parameters", gaussian_model<Dim>(), [](auto& model) {
        model.set_parameters(
            {0.125, std::numeric_limits<double>::quiet_NaN(),
             std::numeric_limits<double>::infinity()});
      });
}

template <int Dim>
std::vector<std::string> monomial_labels() {
  if constexpr (Dim == 1) {
    return {"1", "x", "x^2"};
  }
  if constexpr (Dim == 2) {
    return {"1", "x", "y", "x^2", "xy", "y^2"};
  }
  return {"1", "x", "y", "z", "x^2", "xy", "xz", "y^2", "yz", "z^2"};
}

template <int Dim>
std::vector<std::string> mixed_row_labels(Index num_value_points, Index num_gradient_points) {
  constexpr std::string_view components[] = {"x", "y", "z"};
  std::vector<std::string> labels;
  for (Index i = 0; i < num_value_points; ++i) {
    labels.push_back("value[" + std::to_string(i) + "]");
  }
  for (Index i = 0; i < num_gradient_points; ++i) {
    for (int component = 0; component < Dim; ++component) {
      labels.push_back("gradient[" + std::to_string(i) + "]." +
                       std::string(components[component]));
    }
  }
  return labels;
}

template <int Dim>
Points<Dim> make_points(const std::vector<std::vector<double>>& rows) {
  Points<Dim> points(static_cast<Index>(rows.size()), Dim);
  for (Index row = 0; row < points.rows(); ++row) {
    for (int column = 0; column < Dim; ++column) {
      points(row, column) =
          rows.at(static_cast<std::size_t>(row)).at(static_cast<std::size_t>(column));
    }
  }
  return points;
}

template <int Dim>
void probe_monomial_basis() {
  const auto value_points =
      make_points<Dim>({{2.0, 3.0, 5.0}, {-7.0, 11.0, -13.0}});
  const auto gradient_points =
      make_points<Dim>({{17.0, -19.0, 23.0}, {-29.0, 31.0, -37.0}});
  const auto row_labels =
      mixed_row_labels<Dim>(value_points.rows(), gradient_points.rows());
  const auto all_column_labels = monomial_labels<Dim>();

  for (int degree = 0; degree <= 2; ++degree) {
    polatory::polynomial::MonomialBasis<Dim> basis(degree);
    const auto evaluated = basis.evaluate(value_points, gradient_points);
    auto column_labels = all_column_labels;
    column_labels.resize(static_cast<std::size_t>(basis.basis_size()));

    std::ostringstream fields;
    fields << ",\"dimension\":" << Dim << ",\"degree\":" << basis.degree()
           << ",\"basis_size\":" << basis.basis_size()
           << ",\"column_order\":" << json_string_vector(column_labels)
           << ",\"row_order\":" << json_string_vector(row_labels)
           << ",\"value_points\":" << json_matrix(value_points)
           << ",\"gradient_points\":" << json_matrix(gradient_points)
           << ",\"evaluation\":" << json_matrix(evaluated);
    emit("monomial_basis_observation", fields.str());
  }
}

template <int Dim>
void probe_direct_operator() {
  auto value_points =
      make_points<Dim>({{0.0, 0.0, 0.0}, {0.5, -0.25, 0.125}});
  auto gradient_points =
      make_points<Dim>({{-0.375, 0.625, -0.125}, {0.875, -0.5, 0.75}});

  polatory::Model<Dim> model(
      polatory::rbf::make_rbf<Dim>("th3", {1.25, 0.0}));
  model.set_nugget(0.125);
  polatory::interpolation::DirectOperator<Dim> direct_operator(
      model, value_points, gradient_points);

  MatX dense(direct_operator.size(), direct_operator.size());
  for (Index column = 0; column < direct_operator.size(); ++column) {
    VecX unit = VecX::Zero(direct_operator.size());
    unit(column) = 1.0;
    dense.col(column) = direct_operator(unit);
  }

  auto layout = mixed_row_labels<Dim>(value_points.rows(), gradient_points.rows());
  const auto polynomial_labels = monomial_labels<Dim>();
  for (Index i = 0; i < model.poly_basis_size(); ++i) {
    layout.push_back("polynomial[" + polynomial_labels.at(static_cast<std::size_t>(i)) + "]");
  }

  std::ostringstream fields;
  fields << ",\"dimension\":" << Dim << ",\"family\":\"th3\""
         << ",\"difference_convention\":\"target_minus_source\""
         << ",\"gradient_component_order\":\"point_major\""
         << ",\"layout\":" << json_string_vector(layout)
         << ",\"model\":" << model_state_json(model)
         << ",\"value_points\":" << json_matrix(value_points)
         << ",\"gradient_points\":" << json_matrix(gradient_points)
         << ",\"dense_matrix\":" << json_matrix(dense);
  emit("direct_operator_dense_observation", fields.str());
}

std::string compiler_id() {
#if defined(__clang__)
  return "clang-" + std::to_string(__clang_major__) + "." +
         std::to_string(__clang_minor__) + "." + std::to_string(__clang_patchlevel__);
#elif defined(_MSC_VER)
  return "msvc-" + std::to_string(_MSC_VER);
#elif defined(__GNUC__)
  return "gcc-" + std::to_string(__GNUC__) + "." + std::to_string(__GNUC_MINOR__) + "." +
         std::to_string(__GNUC_PATCHLEVEL__);
#else
  return "unknown";
#endif
}

void emit_manifest() {
  std::ostringstream fields;
  fields << ",\"label\":\"instrumented diagnostic evidence; not acceptance evidence\""
         << ",\"polatory_commit\":" << json_quote(POLATORY_FROZEN_COMMIT)
         << ",\"compiler\":" << json_quote(compiler_id())
         << ",\"eigen_version\":"
         << json_quote(std::to_string(EIGEN_WORLD_VERSION) + "." +
                       std::to_string(EIGEN_MAJOR_VERSION) + "." +
                       std::to_string(EIGEN_MINOR_VERSION))
         << ",\"double_bytes\":" << sizeof(double)
         << ",\"double_is_iec559\":"
         << (std::numeric_limits<double>::is_iec559 ? "true" : "false")
         << ",\"double_encoding\":\"ieee754_binary64_bits_lowercase_hex\""
         << ",\"matrix_encoding\":\"nested_logical_rows\""
         << ",\"comparison_thresholds\":null"
         << ",\"dimensions\":[1,2,3]"
         << ",\"families\":" << json_string_vector(family_names());
  emit("manifest", fields.str());
}

}  // namespace

int main() {
  std::locale::global(std::locale::classic());
  std::cout.imbue(std::locale::classic());

  try {
    emit_manifest();

    probe_all_rbf_families<1>();
    probe_all_rbf_families<2>();
    probe_all_rbf_families<3>();
    probe_rbf_parameter_behavior();

    probe_anisotropy<1>();
    probe_anisotropy<2>();
    probe_anisotropy<3>();

    probe_models<1>();
    probe_models<2>();
    probe_models<3>();

    probe_monomial_basis<1>();
    probe_monomial_basis<2>();
    probe_monomial_basis<3>();

    probe_direct_operator<1>();
    probe_direct_operator<2>();
    probe_direct_operator<3>();

    emit("summary", ",\"records_before_summary\":" + std::to_string(g_record_count) +
                        ",\"status\":\"completed\"");
    return 0;
  } catch (const std::exception& error) {
    emit("fatal", ",\"exception_type\":\"std::exception\",\"what\":" +
                      json_quote(error.what()));
    return 1;
  } catch (...) {
    emit("fatal", ",\"exception_type\":\"unknown\",\"what\":\"\"");
    return 1;
  }
}
