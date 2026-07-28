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
#include <utility>
#include <vector>

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
    "the frozen capture requires Eigen ABI/source version 3.5.0");

constexpr std::string_view kSchema = "rapidrbf-dense-factor-corpus-v1";
constexpr std::string_view kGenerator = "m1-m4-10k-max-fine-and-level0-coarse-v1";
constexpr Index kCoarseScalarTarget = 2048;

struct Workload {
  std::string panel_id;
  std::string case_id;
  std::string accepted_seed;
  std::string geometry_id;
  Index value_rows{};
  Index gradient_rows{};
  Model model;
};

struct Record {
  std::string record_id;
  std::string panel_id;
  std::string case_id;
  std::string accepted_seed;
  std::string geometry_id;
  std::string role;
  std::string assembly_variant;
  std::string assembly_authority;
  std::string matrix_kind{"symmetric_projected"};
  std::string registered_rank_expectation;
  std::string semantic_rank_state{"certificate-missing"};
  Index source_value_rows{};
  Index source_gradient_rows{};
  Index value_rows{};
  Index gradient_rows{};
  Index scalar_order{};
  Index polynomial_order{};
  Index reduced_order{};
  std::string eigen_info;
  bool eigen_positive{};
  double eigen_reduced_backward_error{};
  bool polynomial_invertible{};
  Index polynomial_rank{};
  double polynomial_rcond{};
  std::vector<std::pair<std::string, std::string>> files;
};

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

Points make_points(Index count, std::string_view geometry, std::uint64_t offset) {
  Points points(count, 3);
  for (Index row = 0; row < count; ++row) {
    const auto i = static_cast<std::uint64_t>(row) + offset + 1;
    double x = halton(i, 2);
    double y = halton(i, 3);
    double z = halton(i, 5);

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
      const auto cluster = static_cast<int>(i % 4);
      const double jitter = 0.035;
      const double cx = (cluster == 0 || cluster == 3) ? 0.08 : 0.92;
      const double cy = (cluster == 0 || cluster == 1) ? 0.08 : 0.92;
      const double cz = (cluster == 0 || cluster == 2) ? 0.08 : 0.92;
      x = std::clamp(cx + jitter * (x - 0.5), 0.0, 1.0);
      y = std::clamp(cy + jitter * (y - 0.5), 0.0, 1.0);
      z = std::clamp(cz + jitter * (z - 0.5), 0.0, 1.0);
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
  return points;
}

VecX make_payload(const Points& points, const Points& gradient_points) {
  VecX payload(points.rows() + 3 * gradient_points.rows());
  for (Index i = 0; i < points.rows(); ++i) {
    const double x = points(i, 0);
    const double y = points(i, 1);
    const double z = points(i, 2);
    payload(i) = std::sin(0.7 * x) + 0.3 * std::cos(1.1 * y) + 0.2 * x * z;
  }
  for (Index i = 0; i < gradient_points.rows(); ++i) {
    const double x = gradient_points(i, 0);
    const double y = gradient_points(i, 1);
    const double z = gradient_points(i, 2);
    payload(points.rows() + 3 * i + 0) = 0.7 * std::cos(0.7 * x) + 0.2 * z;
    payload(points.rows() + 3 * i + 1) = -0.33 * std::sin(1.1 * y);
    payload(points.rows() + 3 * i + 2) = 0.2 * x;
  }
  return payload;
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
  gaussian_anisotropy << 0.92, 0.0, 0.08, 0.04, 1.08, 0.0, 0.0, 0.1, 1.35;
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
  result.push_back(Workload{
      "M1-EXP-LOCAL",
      "M1/EXP/10K-ASSIGNED",
      "lower rung of SCL.EXP-ORDINARY-1M",
      "halton-unit-cube-v1",
      10000,
      0,
      make_exp_model(),
  });
  result.push_back(Workload{
      "M2-TH3-CPD",
      "M2/TH3/10K-ASSIGNED",
      "th3 fixed solver panel + FIT.GEOMETRY",
      "nonuniform-boundary",
      10000,
      0,
      make_th3_model(),
  });
  result.push_back(Workload{
      "M3-HERMITE-COMPOSITE",
      "M3/HERMITE/10K-ASSIGNED",
      "lower rung of SCL.HERMITE-COMPOSITE-1M",
      "mixed-hermite-shear",
      7500,
      2500,
      make_hermite_model(),
  });
  result.push_back(Workload{
      "M4-GEOMETRY-FAILURE",
      "M4/GEOMETRY/10K-SELECTED-VALID",
      "FIT.GEOMETRY selected valid cases",
      "clustered-near-boundary",
      10000,
      0,
      make_th3_model(),
  });
  return result;
}

std::vector<Index> ordered_point_indices(Index count,
                                         const std::vector<Index>& polynomial_indices) {
  std::vector<Index> result(polynomial_indices);
  result.reserve(static_cast<std::size_t>(count));
  for (Index i = 0; i < count; ++i) {
    if (!std::binary_search(polynomial_indices.begin(), polynomial_indices.end(), i)) {
      result.push_back(i);
    }
  }
  return result;
}

Index scalar_order(const Domain& domain) {
  return domain.num_points() + 3 * domain.num_grad_points();
}

bool domain_key_less(const Domain& lhs, const Domain& rhs) {
  if (lhs.point_indices != rhs.point_indices) {
    return std::lexicographical_compare(lhs.point_indices.begin(), lhs.point_indices.end(),
                                        rhs.point_indices.begin(), rhs.point_indices.end());
  }
  return std::lexicographical_compare(
      lhs.grad_point_indices.begin(), lhs.grad_point_indices.end(),
      rhs.grad_point_indices.begin(), rhs.grad_point_indices.end());
}

Domain select_max_order_domain(const std::list<Domain>& domains) {
  if (domains.empty()) {
    throw std::runtime_error("domain divider produced no fine domains");
  }
  auto selected = domains.begin();
  for (auto it = std::next(domains.begin()); it != domains.end(); ++it) {
    const auto selected_order = scalar_order(*selected);
    const auto candidate_order = scalar_order(*it);
    if (candidate_order > selected_order ||
        (candidate_order == selected_order && domain_key_less(*it, *selected))) {
      selected = it;
    }
  }
  return *selected;
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

template <typename T>
void write_raw(const std::filesystem::path& path, const std::vector<T>& values) {
  std::ofstream out(path, std::ios::binary);
  if (!out) {
    throw std::runtime_error("cannot open " + path.string());
  }
  out.write(reinterpret_cast<const char*>(values.data()),
            static_cast<std::streamsize>(values.size() * sizeof(T)));
  if (!out) {
    throw std::runtime_error("cannot write " + path.string());
  }
}

void write_f64_vector(const std::filesystem::path& path, const VecX& values) {
  std::vector<double> output(static_cast<std::size_t>(values.rows()));
  for (Index i = 0; i < values.rows(); ++i) {
    output.at(static_cast<std::size_t>(i)) = values(i);
  }
  write_raw(path, output);
}

void write_i64_vector(const std::filesystem::path& path,
                      const std::vector<Index>& values) {
  std::vector<std::int64_t> output;
  output.reserve(values.size());
  for (const auto value : values) {
    output.push_back(static_cast<std::int64_t>(value));
  }
  write_raw(path, output);
}

void write_matrix_row_major(const std::filesystem::path& path, const MatX& matrix) {
  std::vector<double> output;
  output.reserve(static_cast<std::size_t>(matrix.size()));
  for (Index row = 0; row < matrix.rows(); ++row) {
    for (Index column = 0; column < matrix.cols(); ++column) {
      output.push_back(matrix(row, column));
    }
  }
  write_raw(path, output);
}

void write_matrix_lower_row(const std::filesystem::path& path, const MatX& matrix) {
  if (matrix.rows() != matrix.cols()) {
    throw std::invalid_argument("lower-triangle writer requires a square matrix");
  }
  std::vector<double> output;
  output.reserve(static_cast<std::size_t>(matrix.rows() * (matrix.rows() + 1) / 2));
  for (Index row = 0; row < matrix.rows(); ++row) {
    for (Index column = 0; column <= row; ++column) {
      output.push_back(matrix(row, column));
    }
  }
  write_raw(path, output);
}

double matrix_inf_norm(const MatX& matrix) {
  double result = 0.0;
  for (Index row = 0; row < matrix.rows(); ++row) {
    result = std::max(result, matrix.row(row).cwiseAbs().sum());
  }
  return result;
}

double vector_inf_norm(const VecX& vector) {
  return vector.size() == 0 ? 0.0 : vector.cwiseAbs().maxCoeff();
}

double backward_error(const MatX& matrix, const VecX& solution, const VecX& rhs) {
  const double numerator = vector_inf_norm(matrix * solution - rhs);
  const double denominator =
      matrix_inf_norm(matrix) * vector_inf_norm(solution) + vector_inf_norm(rhs);
  return denominator == 0.0 ? (numerator == 0.0 ? 0.0
                                               : std::numeric_limits<double>::infinity())
                            : numerator / denominator;
}

std::string eigen_info(Eigen::ComputationInfo info) {
  switch (info) {
    case Eigen::Success:
      return "Success";
    case Eigen::NumericalIssue:
      return "NumericalIssue";
    case Eigen::NoConvergence:
      return "NoConvergence";
    case Eigen::InvalidInput:
      return "InvalidInput";
  }
  return "Unknown";
}

std::vector<Index> flat_indices(const Domain& domain, Index full_value_rows,
                                bool frozen_literal_mapping) {
  std::vector<Index> result(domain.point_indices);
  result.reserve(static_cast<std::size_t>(scalar_order(domain)));
  const Index gradient_offset =
      frozen_literal_mapping ? domain.num_points() : full_value_rows;
  for (const auto index : domain.grad_point_indices) {
    for (Index component = 0; component < 3; ++component) {
      result.push_back(gradient_offset + 3 * index + component);
    }
  }
  return result;
}

VecX extract_payload(const VecX& payload, const Domain& domain, Index full_value_rows) {
  VecX result(scalar_order(domain));
  for (Index i = 0; i < domain.num_points(); ++i) {
    result(i) = payload(domain.point_indices.at(static_cast<std::size_t>(i)));
  }
  for (Index i = 0; i < domain.num_grad_points(); ++i) {
    const auto global = domain.grad_point_indices.at(static_cast<std::size_t>(i));
    result.segment<3>(domain.num_points() + 3 * i) =
        payload.segment<3>(full_value_rows + 3 * global);
  }
  return result;
}

void add_file(Record& record, std::string name, const std::filesystem::path& relative) {
  record.files.emplace_back(std::move(name), relative.generic_string());
}

Record capture_record(const Workload& workload, const Points& full_points,
                      const Points& full_gradient_points, const VecX& full_payload,
                      const MatX& lagrange_p_full, const Domain& domain,
                      std::string role, bool frozen_literal_mapping,
                      const std::filesystem::path& output_root) {
  const bool literal = frozen_literal_mapping;
  const auto assembly_variant = literal ? "frozen-literal-gradient-row-map"
                                        : "canonical-row-channel-map";
  const auto assembly_authority = literal
                                      ? "research-only-frozen-compatibility"
                                      : "candidate-independent-canonical";
  const auto registered_rank_expectation =
      literal ? "none-research-only"
              : "source-workload-full-rank-expectation";
  const std::string slug = workload.panel_id + "-" + role + "-" +
                           (literal ? "frozen-literal" : "canonical");
  const auto record_dir = output_root / "records" / slug;
  std::filesystem::create_directories(record_dir);

  const auto local_points = full_points(domain.point_indices, polatory::kAll);
  const auto local_gradient_points =
      full_gradient_points(domain.grad_point_indices, polatory::kAll);
  const MatX matrix_a =
      polatory::preconditioner::mat_a(workload.model, local_points,
                                     local_gradient_points);
  const MonomialBasis monomial(workload.model.poly_degree());
  const MatX matrix_p = monomial.evaluate(local_points, local_gradient_points);

  const auto indices =
      flat_indices(domain, full_points.rows(), frozen_literal_mapping);
  const MatX local_lagrange_p = lagrange_p_full(indices, polatory::kAll);
  const Index polynomial_order = workload.model.poly_basis_size();
  const Index order = scalar_order(domain);
  if (order <= polynomial_order) {
    throw std::runtime_error("selected factor block has no reduced degrees of freedom");
  }
  const Index reduced_order = order - polynomial_order;
  MatX q_top =
      -local_lagrange_p.bottomRows(reduced_order).transpose();
  // Preserve the frozen FineGrid/CoarseGrid expression and operation order.
  // This is intentionally not shortened to Q^T A Q.
  const MatX matrix_b =
      q_top.transpose() *
          matrix_a.topLeftCorner(polynomial_order, polynomial_order) * q_top +
      q_top.transpose() *
          matrix_a.topRightCorner(polynomial_order, reduced_order) +
      matrix_a.bottomLeftCorner(reduced_order, polynomial_order) * q_top +
      matrix_a.bottomRightCorner(reduced_order, reduced_order);

  const VecX rhs_d = extract_payload(full_payload, domain, full_points.rows());
  // Preserve the frozen solve's exact operation graph too. Materializing a
  // dense Q and multiplying Q^T*d is algebraically equivalent, but traverses
  // the identity/zero tail and can produce different floating-point rounding.
  const VecX rhs_reduced =
      q_top.transpose() * rhs_d.head(polynomial_order) +
      rhs_d.tail(reduced_order);

  Eigen::LDLT<MatX> ldlt(matrix_b);
  const VecX eigen_solution = ldlt.solve(rhs_reduced);
  const double eigen_error = backward_error(matrix_b, eigen_solution, rhs_reduced);

  const MatX p_top = monomial.evaluate(local_points.topRows(polynomial_order));
  Eigen::FullPivLU<MatX> polynomial_lu(p_top);
  VecX lambda(order);
  lambda.head(polynomial_order) = q_top * eigen_solution;
  lambda.tail(reduced_order) = eigen_solution;
  const VecX polynomial_rhs =
      rhs_d.head(polynomial_order) - matrix_a.topRows(polynomial_order) * lambda;
  const VecX polynomial_solution = polynomial_lu.solve(polynomial_rhs);

  std::vector<Index> eigen_permutation(
      static_cast<std::size_t>(ldlt.transpositionsP().indices().size()));
  for (Index i = 0; i < ldlt.transpositionsP().indices().size(); ++i) {
    eigen_permutation.at(static_cast<std::size_t>(i)) =
        ldlt.transpositionsP().indices()(i);
  }
  std::vector<Index> polynomial_row_permutation(
      static_cast<std::size_t>(polynomial_lu.permutationP().indices().size()));
  std::vector<Index> polynomial_column_permutation(
      static_cast<std::size_t>(polynomial_lu.permutationQ().indices().size()));
  for (Index i = 0; i < polynomial_lu.permutationP().indices().size(); ++i) {
    polynomial_row_permutation.at(static_cast<std::size_t>(i)) =
        polynomial_lu.permutationP().indices()(i);
    polynomial_column_permutation.at(static_cast<std::size_t>(i)) =
        polynomial_lu.permutationQ().indices()(i);
  }

  Record record;
  record.record_id = slug;
  record.panel_id = workload.panel_id;
  record.case_id = workload.case_id;
  record.accepted_seed = workload.accepted_seed;
  record.geometry_id = workload.geometry_id;
  record.role = role;
  record.assembly_variant = assembly_variant;
  record.assembly_authority = assembly_authority;
  record.registered_rank_expectation = registered_rank_expectation;
  record.source_value_rows = workload.value_rows;
  record.source_gradient_rows = workload.gradient_rows;
  record.value_rows = domain.num_points();
  record.gradient_rows = domain.num_grad_points();
  record.scalar_order = order;
  record.polynomial_order = polynomial_order;
  record.reduced_order = reduced_order;
  record.eigen_info = eigen_info(ldlt.info());
  record.eigen_positive = ldlt.isPositive();
  record.eigen_reduced_backward_error = eigen_error;
  record.polynomial_invertible = polynomial_lu.isInvertible();
  record.polynomial_rank = polynomial_lu.rank();
  record.polynomial_rcond = polynomial_lu.rcond();

  const auto relative_dir = std::filesystem::path("records") / slug;
  auto emit_lower = [&](std::string name, const MatX& matrix) {
    const auto relative = relative_dir / (name + ".f64le");
    write_matrix_lower_row(output_root / relative, matrix);
    add_file(record, std::move(name), relative);
  };
  auto emit_matrix = [&](std::string name, const MatX& matrix) {
    const auto relative = relative_dir / (name + ".f64le");
    write_matrix_row_major(output_root / relative, matrix);
    add_file(record, std::move(name), relative);
  };
  auto emit_vector = [&](std::string name, const VecX& vector) {
    const auto relative = relative_dir / (name + ".f64le");
    write_f64_vector(output_root / relative, vector);
    add_file(record, std::move(name), relative);
  };
  auto emit_indices = [&](std::string name, const std::vector<Index>& vector) {
    const auto relative = relative_dir / (name + ".i64le");
    write_i64_vector(output_root / relative, vector);
    add_file(record, std::move(name), relative);
  };

  emit_lower("a_lower", matrix_a);
  emit_matrix("p_row_major", matrix_p);
  emit_matrix("q_top_row_major", q_top);
  emit_lower("b_lower", matrix_b);
  emit_vector("rhs_full", rhs_d);
  emit_vector("rhs_reduced", rhs_reduced);
  emit_vector("eigen_solution_reduced", eigen_solution);
  emit_vector("eigen_solution_lambda", lambda);
  emit_vector("eigen_solution_polynomial", polynomial_solution);
  emit_lower("eigen_ldlt_lower", ldlt.matrixLDLT());
  emit_vector("eigen_ldlt_d", ldlt.vectorD());
  emit_indices("eigen_transpositions", eigen_permutation);
  emit_matrix("polynomial_p_top", p_top);
  emit_matrix("eigen_polynomial_lu", polynomial_lu.matrixLU());
  emit_indices("eigen_polynomial_row_permutation", polynomial_row_permutation);
  emit_indices("eigen_polynomial_column_permutation",
               polynomial_column_permutation);
  emit_indices("domain_value_indices", domain.point_indices);
  emit_indices("domain_gradient_indices", domain.grad_point_indices);
  emit_indices("lagrange_flat_indices", indices);

  return record;
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

void write_manifest(const std::filesystem::path& path,
                    const std::vector<Record>& records) {
  std::ofstream out(path);
  if (!out) {
    throw std::runtime_error("cannot open " + path.string());
  }
  out << "{\n"
      << "  \"schema\": " << json_quote(kSchema) << ",\n"
      << "  \"generator\": " << json_quote(kGenerator) << ",\n"
      << "  \"evidence\": \"instrumented prototype evidence; not acceptance evidence\",\n"
      << "  \"polatory_commit\": " << json_quote(POLATORY_FROZEN_COMMIT) << ",\n"
      << "  \"compiler\": " << json_quote(compiler_id()) << ",\n"
      << "  \"build_mode\": " << json_quote(RAPIDRBF_CAPTURE_BUILD_MODE)
      << ",\n"
      << "  \"floating_point_mode\": "
      << json_quote(RAPIDRBF_CAPTURE_FLOAT_MODE) << ",\n"
      << "  \"eigen_blas\": \"EIGEN_USE_BLAS; oneMKL LP64 sequential 2023.0.0#2\",\n"
      << "  \"projected_matrix_assembly\": \"frozen-four-block-expression-v1\",\n"
      << "  \"projected_rhs_assembly\": \"frozen-qtop-gemv-plus-tail-v1\",\n"
      << "  \"native_artifact_closure\": {\n"
      << "    \"coordinate\": \"intel-mkl 2023.0.0#2; Windows x86_64; LP64; sequential\",\n"
      << "    \"runtime_identity\": \"Intel oneMKL 2023.0-Product Build 20221128\",\n"
      << "    \"sha256\": {\n"
      << "      \"mkl_intel_lp64_dll.lib\": \"487b430c0a2bcca41dc40abcab8cbc18471701b621efb850136f6d45821f5db4\",\n"
      << "      \"mkl_sequential_dll.lib\": \"3859198460bd0d04a617a7fecb9ceb9c18f7e8b14ebcb439a0eebaca7b9d01b2\",\n"
      << "      \"mkl_core_dll.lib\": \"110c0433d4665f8535174059d9042992cd88e566c7b2b13281fd776a7d46cc02\",\n"
      << "      \"mkl_core.2.dll\": \"3e7edb4328abf430b62c7c75e33447042dc8033f0cc75910708fd3bb5f27c792\",\n"
      << "      \"mkl_sequential.2.dll\": \"478fda28a98021fb7f95b27b2876cac7346d77c4a491003ba0f50baf17b66fe3\",\n"
      << "      \"mkl_def.2.dll\": \"0aff76a9a8c4618c1f467bf08334ec3a93e92ada04b62f31864c8f052bea9745\",\n"
      << "      \"mkl_avx2.2.dll\": \"cc85f0c3b1f0f02998a14923037873530645a77039e95a6a3fb90a7d01468d41\"\n"
      << "    }\n"
      << "  },\n"
      << "  \"eigen_version\": "
      << json_quote(std::to_string(EIGEN_WORLD_VERSION) + "." +
                    std::to_string(EIGEN_MAJOR_VERSION) + "." +
                    std::to_string(EIGEN_MINOR_VERSION))
      << ",\n"
      << "  \"double_bytes\": " << sizeof(double) << ",\n"
      << "  \"little_endian\": "
      << (std::endian::native == std::endian::little ? "true" : "false")
      << ",\n"
      << "  \"selection_rule\": "
      << json_quote(
             "each M1-M4 10k source: lexicographically first maximum scalar-order "
             "fine domain plus the selection returned by frozen DomainDivider "
             "at coarse target 2048")
      << ",\n"
      << "  \"records\": [\n";

  for (std::size_t i = 0; i < records.size(); ++i) {
    const auto& record = records.at(i);
    out << "    {\n"
        << "      \"record_id\": " << json_quote(record.record_id) << ",\n"
        << "      \"panel_id\": " << json_quote(record.panel_id) << ",\n"
        << "      \"case_id\": " << json_quote(record.case_id) << ",\n"
        << "      \"accepted_seed\": " << json_quote(record.accepted_seed)
        << ",\n"
        << "      \"geometry_id\": " << json_quote(record.geometry_id) << ",\n"
        << "      \"role\": " << json_quote(record.role) << ",\n"
        << "      \"assembly_variant\": "
        << json_quote(record.assembly_variant) << ",\n"
        << "      \"assembly_authority\": "
        << json_quote(record.assembly_authority) << ",\n"
        << "      \"matrix_kind\": " << json_quote(record.matrix_kind) << ",\n"
        << "      \"registered_rank_expectation\": "
        << json_quote(record.registered_rank_expectation) << ",\n"
        << "      \"semantic_rank_state\": "
        << json_quote(record.semantic_rank_state) << ",\n"
        << "      \"source_value_rows\": " << record.source_value_rows << ",\n"
        << "      \"source_gradient_rows\": " << record.source_gradient_rows
        << ",\n"
        << "      \"value_rows\": " << record.value_rows << ",\n"
        << "      \"gradient_rows\": " << record.gradient_rows << ",\n"
        << "      \"scalar_order\": " << record.scalar_order << ",\n"
        << "      \"polynomial_order\": " << record.polynomial_order << ",\n"
        << "      \"reduced_order\": " << record.reduced_order << ",\n"
        << "      \"frozen_eigen_baseline\": {\n"
        << "        \"ldlt_info\": " << json_quote(record.eigen_info) << ",\n"
        << "        \"ldlt_is_positive\": "
        << (record.eigen_positive ? "true" : "false") << ",\n"
        << "        \"reduced_backward_error\": "
        << std::setprecision(17) << record.eigen_reduced_backward_error << ",\n"
        << "        \"polynomial_invertible\": "
        << (record.polynomial_invertible ? "true" : "false") << ",\n"
        << "        \"polynomial_rank\": " << record.polynomial_rank << ",\n"
        << "        \"polynomial_rcond\": " << std::setprecision(17)
        << record.polynomial_rcond << "\n"
        << "      },\n"
        << "      \"files\": {\n";
    for (std::size_t file_index = 0; file_index < record.files.size();
         ++file_index) {
      const auto& [name, file] = record.files.at(file_index);
      out << "        " << json_quote(name) << ": " << json_quote(file);
      out << (file_index + 1 == record.files.size() ? "\n" : ",\n");
    }
    out << "      }\n"
        << "    }" << (i + 1 == records.size() ? "\n" : ",\n");
  }
  out << "  ]\n}\n";
}

}  // namespace

int main(int argc, char** argv) {
  try {
    if (argc != 2) {
      std::cerr << "usage: rapidrbf_dense_factor_capture OUTPUT_DIR\n";
      return 2;
    }
    if (sizeof(double) != 8 || !std::numeric_limits<double>::is_iec559 ||
        std::endian::native != std::endian::little) {
      throw std::runtime_error(
          "capture requires little-endian IEC 60559 binary64");
    }

    const std::filesystem::path output_root(argv[1]);
    std::filesystem::create_directories(output_root / "records");
    std::vector<Record> records;

    for (const auto& workload : workloads()) {
      std::cout << "materializing " << workload.case_id << std::endl;
      const auto points =
          make_points(workload.value_rows, workload.geometry_id, 0);
      const auto gradient_points =
          make_points(workload.gradient_rows, workload.geometry_id, 20000);
      const auto payload = make_payload(points, gradient_points);

      const UnisolventPointSet unisolvent(points, workload.model.poly_degree());
      const auto polynomial_indices = unisolvent.point_indices();
      const LagrangeBasis lagrange(
          workload.model.poly_degree(),
          points(polynomial_indices, polatory::kAll));
      const MatX lagrange_p_full = lagrange.evaluate(points, gradient_points);

      const auto point_indices =
          ordered_point_indices(points.rows(), polynomial_indices);
      std::vector<Index> gradient_indices(
          static_cast<std::size_t>(gradient_points.rows()));
      std::iota(gradient_indices.begin(), gradient_indices.end(), 0);

      DomainDivider divider(points, gradient_points, point_indices,
                            gradient_indices, polynomial_indices);
      auto [coarse_points, coarse_gradients] =
          divider.choose_coarse_points(kCoarseScalarTarget);
      const Domain fine = select_max_order_domain(divider.domains());
      const Domain coarse =
          make_coarse_domain(std::move(coarse_points),
                             std::move(coarse_gradients));

      records.push_back(capture_record(
          workload, points, gradient_points, payload, lagrange_p_full, fine,
          "max-order-fine", false, output_root));
      records.push_back(capture_record(
          workload, points, gradient_points, payload, lagrange_p_full, coarse,
          "level0-coarse", false, output_root));

      if (workload.panel_id == "M3-HERMITE-COMPOSITE") {
        records.push_back(capture_record(
            workload, points, gradient_points, payload, lagrange_p_full, fine,
            "max-order-fine", true, output_root));
        records.push_back(capture_record(
            workload, points, gradient_points, payload, lagrange_p_full,
            coarse, "level0-coarse", true, output_root));
      }
    }

    write_manifest(output_root / "manifest.raw.json", records);
    std::cout << "captured " << records.size() << " records at "
              << output_root.string() << std::endl;
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "capture failed: " << error.what() << std::endl;
    return 1;
  }
}
