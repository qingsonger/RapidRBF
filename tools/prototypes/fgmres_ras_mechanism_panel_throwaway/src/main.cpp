// THROWAWAY PROTOTYPE: Issue 32 FGMRES/RAS mechanism panel.
//
// Question: under one hash-bound canonical M1-M4 hierarchy/factor corpus and
// one fixed matrix action, which restarted right-FGMRES window,
// orthogonalization policy, and same-hierarchy RAS topology are robust enough
// to carry into the 100k resource/storage experiment?
//
// This is evidence code, not a production solver.  The Polatory action is a
// frozen observation route.  Local factors are run-scoped and independently
// checked against the repaired frozen-system reference; they are not a
// release-admitted factor backend.

#include <windows.h>

#include <bcrypt.h>
#include <psapi.h>

#include <Eigen/Cholesky>
#include <Eigen/Core>
#include <Eigen/LU>

#include <mkl_service.h>
#include <omp.h>

#include <boost/multiprecision/cpp_int.hpp>
#include <boost/property_tree/json_parser.hpp>
#include <boost/property_tree/ptree.hpp>

#include <algorithm>
#include <array>
#include <bit>
#include <chrono>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <memory>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <unordered_map>
#include <utility>
#include <vector>

#include <polatory/common/orthonormalize.hpp>
#include <polatory/interpolation/direct_evaluator.hpp>
#include <polatory/interpolation/operator.hpp>
#include <polatory/model.hpp>
#include <polatory/polynomial/monomial_basis.hpp>
#include <polatory/preconditioner/mat_a.hpp>
#include <polatory/rbf/make_rbf.hpp>
#include <polatory/types.hpp>

namespace fs = std::filesystem;
namespace pt = boost::property_tree;
using boost::multiprecision::cpp_int;
using Eigen::Dynamic;
using Eigen::Matrix;
using Eigen::MatrixXd;
using Eigen::VectorXd;
using RowMatrixXd = Matrix<double, Dynamic, Dynamic, Eigen::RowMajor>;
using Index = Eigen::Index;

constexpr double kMachineEpsilon = 0x1p-52;
constexpr double kUnitRoundoff = 0x1p-53;
constexpr double kFitTolerance = 0x1p-24;
// Polatory's finite sampled-accuracy search cannot construct the registered
// mixed-gradient evaluator at the fit-scale requests.  Its special zero request
// deterministically selects order=12,d=8 without claiming a certified bound.
// This remains a search/screening route only; complete direct evaluation is the
// success authority.
constexpr double kOperatorAccuracy = 0.0;
constexpr double kCpdTolerance = 0x1p-32;
constexpr int kMaximumIterations = 100;
constexpr int kMaximumPreconditionerOperatorActions = 240;
constexpr std::array<int, 3> kWindows{5, 32, 64};
constexpr std::string_view kCorpusDigest =
    "38f39fee8b4059cd2619df4bbfabb6f7159b41df1511907e0346c32642737f79";
constexpr std::string_view kRawManifestSha =
    "cf5aaa1e3fe6bf51c3f24f13455ac1036e7ec591668c18ec4c86f3243aa07f54";
constexpr std::string_view kReferenceManifestSha =
    "6ed634a288145dfb3688e6e480f9519c1dbbe5c528aa9bb4b825eb57bc1b584a";

[[noreturn]] void fail(const std::string& message) {
  throw std::runtime_error(message);
}

std::string lower_ascii(std::string value) {
  std::transform(value.begin(), value.end(), value.begin(), [](unsigned char ch) {
    return static_cast<char>(std::tolower(ch));
  });
  return value;
}

std::string json_escape(std::string_view input) {
  std::ostringstream out;
  for (const char ch : input) {
    switch (ch) {
      case '\\':
        out << "\\\\";
        break;
      case '"':
        out << "\\\"";
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
        if (static_cast<unsigned char>(ch) < 0x20) {
          out << "\\u" << std::hex << std::setw(4) << std::setfill('0')
              << static_cast<int>(static_cast<unsigned char>(ch)) << std::dec;
        } else {
          out << ch;
        }
    }
  }
  return out.str();
}

std::string sha256_bytes(const std::byte* data, std::size_t size) {
  BCRYPT_ALG_HANDLE algorithm{};
  BCRYPT_HASH_HANDLE hash{};
  DWORD object_bytes{};
  DWORD result_bytes{};
  DWORD digest_bytes{};
  if (BCryptOpenAlgorithmProvider(&algorithm, BCRYPT_SHA256_ALGORITHM, nullptr, 0) != 0 ||
      BCryptGetProperty(algorithm, BCRYPT_OBJECT_LENGTH,
                        reinterpret_cast<PUCHAR>(&object_bytes), sizeof(object_bytes),
                        &result_bytes, 0) != 0 ||
      BCryptGetProperty(algorithm, BCRYPT_HASH_LENGTH,
                        reinterpret_cast<PUCHAR>(&digest_bytes), sizeof(digest_bytes),
                        &result_bytes, 0) != 0) {
    fail("cannot initialize Windows SHA-256 provider");
  }
  std::vector<UCHAR> object(object_bytes);
  std::vector<UCHAR> digest(digest_bytes);
  if (BCryptCreateHash(algorithm, &hash, object.data(), object_bytes, nullptr, 0, 0) != 0 ||
      (size != 0 &&
       BCryptHashData(hash, reinterpret_cast<PUCHAR>(const_cast<std::byte*>(data)),
                      static_cast<ULONG>(size), 0) != 0) ||
      BCryptFinishHash(hash, digest.data(), digest_bytes, 0) != 0) {
    if (hash != nullptr) {
      BCryptDestroyHash(hash);
    }
    BCryptCloseAlgorithmProvider(algorithm, 0);
    fail("cannot calculate SHA-256");
  }
  BCryptDestroyHash(hash);
  BCryptCloseAlgorithmProvider(algorithm, 0);
  std::ostringstream out;
  out << std::hex << std::setfill('0');
  for (const auto byte : digest) {
    out << std::setw(2) << static_cast<unsigned>(byte);
  }
  return out.str();
}

std::string sha256_file(const fs::path& path) {
  std::ifstream input(path, std::ios::binary);
  if (!input) {
    fail("cannot open for hashing: " + path.string());
  }
  BCRYPT_ALG_HANDLE algorithm{};
  BCRYPT_HASH_HANDLE hash{};
  DWORD object_bytes{};
  DWORD result_bytes{};
  DWORD digest_bytes{};
  if (BCryptOpenAlgorithmProvider(&algorithm, BCRYPT_SHA256_ALGORITHM, nullptr, 0) != 0 ||
      BCryptGetProperty(algorithm, BCRYPT_OBJECT_LENGTH,
                        reinterpret_cast<PUCHAR>(&object_bytes), sizeof(object_bytes),
                        &result_bytes, 0) != 0 ||
      BCryptGetProperty(algorithm, BCRYPT_HASH_LENGTH,
                        reinterpret_cast<PUCHAR>(&digest_bytes), sizeof(digest_bytes),
                        &result_bytes, 0) != 0) {
    fail("cannot initialize file SHA-256 provider");
  }
  std::vector<UCHAR> object(object_bytes);
  std::vector<UCHAR> digest(digest_bytes);
  if (BCryptCreateHash(algorithm, &hash, object.data(), object_bytes, nullptr, 0, 0) != 0) {
    BCryptCloseAlgorithmProvider(algorithm, 0);
    fail("cannot create file SHA-256 state");
  }
  std::vector<char> buffer(1 << 20);
  while (input) {
    input.read(buffer.data(), static_cast<std::streamsize>(buffer.size()));
    const auto count = input.gcount();
    if (count > 0 &&
        BCryptHashData(hash, reinterpret_cast<PUCHAR>(buffer.data()),
                       static_cast<ULONG>(count), 0) != 0) {
      BCryptDestroyHash(hash);
      BCryptCloseAlgorithmProvider(algorithm, 0);
      fail("cannot update file SHA-256");
    }
  }
  if (BCryptFinishHash(hash, digest.data(), digest_bytes, 0) != 0) {
    BCryptDestroyHash(hash);
    BCryptCloseAlgorithmProvider(algorithm, 0);
    fail("cannot finish file SHA-256");
  }
  BCryptDestroyHash(hash);
  BCryptCloseAlgorithmProvider(algorithm, 0);
  std::ostringstream out;
  out << std::hex << std::setfill('0');
  for (const auto byte : digest) {
    out << std::setw(2) << static_cast<unsigned>(byte);
  }
  return out.str();
}

struct ProcessMemory {
  std::uint64_t current_working_set_bytes{};
  std::uint64_t peak_working_set_bytes{};
};

ProcessMemory process_memory() {
  PROCESS_MEMORY_COUNTERS_EX counters{};
  counters.cb = sizeof(counters);
  if (GetProcessMemoryInfo(
          GetCurrentProcess(),
          reinterpret_cast<PROCESS_MEMORY_COUNTERS*>(&counters),
          sizeof(counters)) == 0) {
    fail("cannot read process memory counters");
  }
  return {static_cast<std::uint64_t>(counters.WorkingSetSize),
          static_cast<std::uint64_t>(counters.PeakWorkingSetSize)};
}

struct Artifact {
  fs::path path;
  std::uint64_t bytes{};
  std::string sha256;
  std::string dtype;
  std::string encoding;
  std::vector<std::size_t> shape;
};

std::vector<std::size_t> size_array(const pt::ptree& tree) {
  std::vector<std::size_t> result;
  for (const auto& [unused, value] : tree) {
    static_cast<void>(unused);
    result.push_back(value.get_value<std::size_t>());
  }
  return result;
}

std::vector<std::string> string_array(const pt::ptree& tree) {
  std::vector<std::string> result;
  result.reserve(tree.size());
  for (const auto& [unused, value] : tree) {
    static_cast<void>(unused);
    result.push_back(value.get_value<std::string>());
  }
  return result;
}

class Corpus {
 public:
  explicit Corpus(fs::path root) : root_(std::move(root)) {
    const auto lock_path = root_ / "manifest.lock.json";
    const auto raw_path = root_ / "hierarchy.manifest.raw.json";
    pt::read_json(lock_path.string(), lock_);
    if (lock_.get<std::string>("schema") !=
            "rapidrbf-canonical-hierarchy-corpus-lock-v3" ||
        lock_.get<std::string>("corpus_sha256") != kCorpusDigest ||
        lock_.get<std::string>("raw_manifest.sha256") != kRawManifestSha) {
      fail("canonical hierarchy lock identity differs");
    }
    if (sha256_file(raw_path) != kRawManifestSha) {
      fail("canonical raw manifest SHA-256 differs");
    }
    for (const auto& [id, node] : lock_.get_child("artifacts")) {
      Artifact artifact;
      artifact.path = root_ / fs::path(node.get<std::string>("path"));
      artifact.bytes = node.get<std::uint64_t>("bytes");
      artifact.sha256 = node.get<std::string>("sha256");
      artifact.dtype = node.get<std::string>("dtype");
      artifact.encoding = node.get<std::string>("encoding");
      artifact.shape = size_array(node.get_child("shape"));
      artifacts_.emplace(id, std::move(artifact));
    }
    pt::read_json(raw_path.string(), raw_);
    if (raw_.get<std::string>("schema") !=
            "rapidrbf-canonical-hierarchy-admission-corpus-v3" ||
        raw_.get<std::size_t>("counts.workloads") != 12 ||
        raw_.get<std::size_t>("counts.blocks") != 204 ||
        raw_.get<std::size_t>("counts.factor_sources") != 216) {
      fail("canonical hierarchy manifest topology differs");
    }
  }

  const pt::ptree& raw() const { return raw_; }

  const Artifact& artifact(const std::string& id) const {
    const auto iterator = artifacts_.find(id);
    if (iterator == artifacts_.end()) {
      fail("unknown artifact: " + id);
    }
    return iterator->second;
  }

  template <typename T>
  std::vector<T> read_vector(const std::string& id, std::string_view dtype) const {
    const auto& item = artifact(id);
    if (item.dtype != dtype || item.bytes % sizeof(T) != 0) {
      fail("artifact dtype/size differs: " + id);
    }
    if (!fs::is_regular_file(item.path) || fs::file_size(item.path) != item.bytes ||
        sha256_file(item.path) != item.sha256) {
      fail("artifact identity differs: " + id);
    }
    std::vector<T> result(static_cast<std::size_t>(item.bytes / sizeof(T)));
    std::ifstream input(item.path, std::ios::binary);
    input.read(reinterpret_cast<char*>(result.data()),
               static_cast<std::streamsize>(item.bytes));
    if (!input || input.peek() != std::ifstream::traits_type::eof()) {
      fail("artifact read failed: " + id);
    }
    return result;
  }

  MatrixXd read_row_matrix(const std::string& id) const {
    const auto& item = artifact(id);
    if (item.shape.size() != 2) {
      fail("matrix artifact has non-matrix shape: " + id);
    }
    const auto values = read_vector<double>(id, "f64");
    const auto rows = static_cast<Index>(item.shape[0]);
    const auto columns = static_cast<Index>(item.shape[1]);
    if (values.size() != static_cast<std::size_t>(rows * columns)) {
      fail("matrix artifact element count differs: " + id);
    }
    Eigen::Map<const RowMatrixXd> mapped(values.data(), rows, columns);
    return MatrixXd(mapped);
  }

  VectorXd read_eigen_vector(const std::string& id) const {
    const auto values = read_vector<double>(id, "f64");
    return Eigen::Map<const VectorXd>(values.data(),
                                     static_cast<Index>(values.size()));
  }

  MatrixXd read_lower_matrix(const std::string& id) const {
    const auto& item = artifact(id);
    if (item.shape.size() != 2 || item.shape[0] != item.shape[1] ||
        item.encoding != "lower-triangle-row-major-packed") {
      fail("lower matrix artifact shape/encoding differs: " + id);
    }
    const auto values = read_vector<double>(id, "f64");
    const auto n = static_cast<Index>(item.shape[0]);
    if (values.size() != static_cast<std::size_t>(n * (n + 1) / 2)) {
      fail("packed lower artifact element count differs: " + id);
    }
    MatrixXd result(n, n);
    for (Index row = 0; row < n; ++row) {
      for (Index column = 0; column <= row; ++column) {
        const double value = values[static_cast<std::size_t>(
            row * (row + 1) / 2 + column)];
        result(row, column) = value;
        result(column, row) = value;
      }
    }
    return result;
  }

 private:
  fs::path root_;
  pt::ptree lock_;
  pt::ptree raw_;
  std::unordered_map<std::string, Artifact> artifacts_;
};

struct Dyadic {
  cpp_int mantissa{};
  std::int64_t exponent{};

  static Dyadic zero() { return {}; }

  static Dyadic from_mpfr_hex(const std::string& text) {
    bool negative = false;
    std::string unsigned_text = text;
    if (!unsigned_text.empty() && unsigned_text.front() == '-') {
      negative = true;
      unsigned_text.erase(unsigned_text.begin());
    }
    std::int64_t radix_exponent = 0;
    const auto at = unsigned_text.find('@');
    if (at != std::string::npos) {
      radix_exponent = std::stoll(unsigned_text.substr(at + 1));
      unsigned_text.resize(at);
    }
    const auto dot = unsigned_text.find('.');
    const std::size_t fractional =
        dot == std::string::npos ? 0 : unsigned_text.size() - dot - 1;
    if (dot != std::string::npos) {
      unsigned_text.erase(dot, 1);
    }
    cpp_int value = 0;
    for (const char ch : unsigned_text) {
      unsigned digit{};
      if (ch >= '0' && ch <= '9') {
        digit = static_cast<unsigned>(ch - '0');
      } else if (ch >= 'a' && ch <= 'f') {
        digit = static_cast<unsigned>(ch - 'a' + 10);
      } else if (ch >= 'A' && ch <= 'F') {
        digit = static_cast<unsigned>(ch - 'A' + 10);
      } else {
        fail("invalid MPFR hexadecimal endpoint");
      }
      value <<= 4;
      value += digit;
    }
    if (negative) {
      value = -value;
    }
    return {value, 4 * (radix_exponent - static_cast<std::int64_t>(fractional))};
  }

  static Dyadic from_f64(double value) {
    if (!std::isfinite(value)) {
      fail("non-finite binary64 cannot be represented as a dyadic");
    }
    const auto bits = std::bit_cast<std::uint64_t>(value);
    const bool negative = (bits >> 63U) != 0;
    const auto exponent_bits = static_cast<unsigned>((bits >> 52U) & 0x7ffU);
    const auto fraction = bits & ((std::uint64_t{1} << 52U) - 1U);
    if (exponent_bits == 0 && fraction == 0) {
      return zero();
    }
    cpp_int mantissa =
        exponent_bits == 0 ? cpp_int(fraction)
                           : cpp_int((std::uint64_t{1} << 52U) | fraction);
    if (negative) {
      mantissa = -mantissa;
    }
    const std::int64_t exponent =
        exponent_bits == 0 ? -1074 : static_cast<std::int64_t>(exponent_bits) - 1023 - 52;
    return {mantissa, exponent};
  }

  cpp_int scaled(std::int64_t target_exponent) const {
    if (exponent < target_exponent) {
      fail("invalid dyadic scale direction");
    }
    return mantissa << static_cast<unsigned long long>(exponent - target_exponent);
  }

  int compare(const Dyadic& other) const {
    const auto common = std::min(exponent, other.exponent);
    const auto left = scaled(common);
    const auto right = other.scaled(common);
    return left < right ? -1 : (left > right ? 1 : 0);
  }

  Dyadic subtract(const Dyadic& other) const {
    const auto common = std::min(exponent, other.exponent);
    return {scaled(common) - other.scaled(common), common};
  }

  Dyadic absolute() const {
    return {mantissa < 0 ? -mantissa : mantissa, exponent};
  }

  Dyadic multiply(const Dyadic& other) const {
    return {mantissa * other.mantissa, exponent + other.exponent};
  }
};

struct ReferenceRhs {
  std::string family;
  std::string rhs_sha256;
  Dyadic scale_lower;
  Dyadic scale_upper;
  Dyadic threshold;
  std::vector<Dyadic> lower;
  std::vector<Dyadic> upper;
};

struct ReferenceEntry {
  std::size_t dimension{};
  std::string source_sha256;
  std::vector<ReferenceRhs> rhs;
};

using ReferenceMap = std::unordered_map<std::string, ReferenceEntry>;

ReferenceMap load_references(const fs::path& path,
                             const std::set<std::string>& wanted_sources) {
  if (sha256_file(path) != kReferenceManifestSha) {
    fail("repaired factor reference manifest SHA-256 differs");
  }
  std::cout << "  parsing repaired frozen-system reference manifest...\n";
  pt::ptree root;
  pt::read_json(path.string(), root);
  if (root.get<std::string>("schema") !=
          "RapidRBF/ProjectedFactorReferenceManifest/v1" ||
      root.get<std::string>("disposition") != "CERTIFIED_REFERENCE" ||
      root.get<std::size_t>("unique_matrix_payloads") != 179 ||
      root.get<std::size_t>("certified_references") != 537 ||
      root.get<std::size_t>("indeterminate_references") != 0 ||
      root.get<bool>("candidate_inputs_observed")) {
    fail("repaired factor reference authority differs");
  }
  ReferenceMap result;
  for (const auto& [unused, node] : root.get_child("entries")) {
    static_cast<void>(unused);
    const auto source_sha = node.get<std::string>("source_sha256");
    if (!wanted_sources.contains(source_sha)) {
      continue;
    }
    ReferenceEntry entry;
    entry.dimension = node.get<std::size_t>("dimension");
    entry.source_sha256 = source_sha;
    for (const auto& [rhs_unused, rhs_node] : node.get_child("rhs")) {
      static_cast<void>(rhs_unused);
      ReferenceRhs rhs;
      rhs.family = rhs_node.get<std::string>("family");
      rhs.rhs_sha256 = rhs_node.get<std::string>("rhs_sha256");
      if (rhs_node.get<std::string>("status") != "CERTIFIED_REFERENCE") {
        fail("wanted repaired factor reference is not certified");
      }
      rhs.scale_lower =
          Dyadic::from_mpfr_hex(rhs_node.get<std::string>("scale_lower_hex"));
      rhs.scale_upper =
          Dyadic::from_mpfr_hex(rhs_node.get<std::string>("scale_upper_hex"));
      rhs.threshold =
          Dyadic::from_mpfr_hex(rhs_node.get<std::string>("solution_threshold_hex"));
      const auto lowers =
          string_array(rhs_node.get_child("enclosure_lower_mpfr_hex"));
      const auto uppers =
          string_array(rhs_node.get_child("enclosure_upper_mpfr_hex"));
      if (lowers.size() != entry.dimension || uppers.size() != entry.dimension) {
        fail("wanted repaired factor enclosure shape differs");
      }
      rhs.lower.reserve(entry.dimension);
      rhs.upper.reserve(entry.dimension);
      for (std::size_t i = 0; i < entry.dimension; ++i) {
        rhs.lower.push_back(Dyadic::from_mpfr_hex(lowers[i]));
        rhs.upper.push_back(Dyadic::from_mpfr_hex(uppers[i]));
      }
      entry.rhs.push_back(std::move(rhs));
    }
    if (entry.rhs.size() != 3) {
      fail("wanted repaired factor reference family count differs");
    }
    result.emplace(source_sha, std::move(entry));
  }
  if (result.size() != wanted_sources.size()) {
    fail("repaired factor reference is missing a wanted matrix");
  }
  return result;
}

struct ReferenceJudgment {
  std::string status;
};

ReferenceJudgment judge_reference(const ReferenceRhs& authority,
                                  const VectorXd& candidate) {
  if (candidate.size() != static_cast<Index>(authority.lower.size())) {
    fail("candidate/reference solution shape differs");
  }
  Dyadic distance_lower = Dyadic::zero();
  Dyadic distance_upper = Dyadic::zero();
  for (Index i = 0; i < candidate.size(); ++i) {
    if (!std::isfinite(candidate(i))) {
      return {"FAIL"};
    }
    const auto value = Dyadic::from_f64(candidate(i));
    const auto& lower = authority.lower[static_cast<std::size_t>(i)];
    const auto& upper = authority.upper[static_cast<std::size_t>(i)];
    if (lower.compare(upper) > 0) {
      fail("reference enclosure endpoints are reversed");
    }
    Dyadic component_lower;
    if (value.compare(lower) < 0) {
      component_lower = lower.subtract(value);
    } else if (value.compare(upper) > 0) {
      component_lower = value.subtract(upper);
    } else {
      component_lower = Dyadic::zero();
    }
    const auto to_lower = value.subtract(lower).absolute();
    const auto to_upper = value.subtract(upper).absolute();
    const auto component_upper =
        to_lower.compare(to_upper) >= 0 ? to_lower : to_upper;
    if (component_lower.compare(distance_lower) > 0) {
      distance_lower = component_lower;
    }
    if (component_upper.compare(distance_upper) > 0) {
      distance_upper = component_upper;
    }
  }
  const auto pass_limit = authority.threshold.multiply(authority.scale_lower);
  const auto fail_limit = authority.threshold.multiply(authority.scale_upper);
  if (distance_upper.compare(pass_limit) <= 0) {
    return {"PASS"};
  }
  if (distance_lower.compare(fail_limit) > 0) {
    return {"FAIL"};
  }
  return {"INDETERMINATE"};
}

struct DoubleDouble {
  double hi{};
  double lo{};
};

DoubleDouble two_sum(double a, double b) {
  const double sum = a + b;
  const double b_virtual = sum - a;
  const double error = (a - (sum - b_virtual)) + (b - b_virtual);
  return {sum, error};
}

DoubleDouble quick_two_sum(double a, double b) {
  const double sum = a + b;
  return {sum, b - (sum - a)};
}

DoubleDouble add(DoubleDouble a, DoubleDouble b) {
  const auto first = two_sum(a.hi, b.hi);
  const auto second = two_sum(a.lo, b.lo);
  const auto middle = two_sum(first.lo, second.hi);
  const auto high = quick_two_sum(first.hi, middle.hi);
  return quick_two_sum(high.hi, high.lo + middle.lo + second.lo);
}

DoubleDouble product(double a, double b) {
  const double high = a * b;
  return {high, std::fma(a, b, -high)};
}

VectorXd double_double_residual(const MatrixXd& matrix, const VectorXd& x,
                                const VectorXd& rhs) {
  VectorXd residual(rhs.size());
  for (Index row = 0; row < matrix.rows(); ++row) {
    DoubleDouble sum{rhs(row), 0.0};
    for (Index column = 0; column < matrix.cols(); ++column) {
      auto term = product(matrix(row, column), x(column));
      term.hi = -term.hi;
      term.lo = -term.lo;
      sum = add(sum, term);
    }
    residual(row) = sum.hi + sum.lo;
  }
  return residual;
}

double matrix_inf_norm(const MatrixXd& matrix) {
  return matrix.cwiseAbs().rowwise().sum().maxCoeff();
}

double reduced_backward_error(const MatrixXd& matrix, const VectorXd& solution,
                              const VectorXd& rhs, bool double_double) {
  const VectorXd residual =
      double_double ? double_double_residual(matrix, solution, rhs)
                    : rhs - matrix * solution;
  const double denominator =
      matrix_inf_norm(matrix) * solution.lpNorm<Eigen::Infinity>() +
      rhs.lpNorm<Eigen::Infinity>();
  const double numerator = residual.lpNorm<Eigen::Infinity>();
  return denominator == 0.0 ? (numerator == 0.0 ? 0.0
                                               : std::numeric_limits<double>::infinity())
                            : numerator / denominator;
}

MatrixXd declared_solutions(Index dimension) {
  MatrixXd result(dimension, 3);
  for (Index row = 0; row < dimension; ++row) {
    result(row, 0) = 1.0 + static_cast<double>(row % 17) / 17.0;
    result(row, 1) = row % 2 == 0 ? 1.0 : -1.0;
    const int exponent = static_cast<int>(row % 21) - 10;
    result(row, 2) =
        (row % 2 == 0 ? 1.0 : -1.0) * std::ldexp(1.0, exponent);
  }
  return result;
}

MatrixXd manufactured_rhs(const MatrixXd& matrix, bool symmetric) {
  const Index n = matrix.rows();
  const MatrixXd expected = declared_solutions(n);
  MatrixXd rhs = MatrixXd::Zero(n, 3);
  if (symmetric) {
    for (Index row = 0; row < n; ++row) {
      for (Index column = 0; column <= row; ++column) {
        const double value = matrix(row, column);
        for (Index family = 0; family < 3; ++family) {
          rhs(row, family) += value * expected(column, family);
          if (row != column) {
            rhs(column, family) += value * expected(row, family);
          }
        }
      }
    }
  } else {
    for (Index row = 0; row < n; ++row) {
      for (Index column = 0; column < n; ++column) {
        const double value = matrix(row, column);
        for (Index family = 0; family < 3; ++family) {
          rhs(row, family) += value * expected(column, family);
        }
      }
    }
  }
  return rhs;
}

std::string sha256_vector(const VectorXd& vector) {
  return sha256_bytes(reinterpret_cast<const std::byte*>(vector.data()),
                      static_cast<std::size_t>(vector.size()) * sizeof(double));
}

struct FactorQualification {
  bool pass{};
  double reconstruction_relative_inf{};
  double maximum_backward_error{};
  int reference_passes{};
  int refinements{};
  std::string reason;
};

template <typename Decomposition>
std::pair<VectorXd, int> refined_solve(const MatrixXd& matrix,
                                       const Decomposition& decomposition,
                                       const VectorXd& rhs,
                                       const ReferenceRhs* authority) {
  VectorXd solution = decomposition.solve(rhs);
  int refinements = 0;
  for (; refinements < 5; ++refinements) {
    const double backward =
        reduced_backward_error(matrix, solution, rhs, true);
    const bool reference_pass =
        authority == nullptr || judge_reference(*authority, solution).status == "PASS";
    if (backward <= 64.0 * static_cast<double>(matrix.rows()) * kUnitRoundoff &&
        reference_pass) {
      break;
    }
    const VectorXd residual = double_double_residual(matrix, solution, rhs);
    const VectorXd correction = decomposition.solve(residual);
    solution += correction;
  }
  return {solution, refinements};
}

template <typename Decomposition>
FactorQualification qualify_factor(const MatrixXd& matrix,
                                   const Decomposition& decomposition,
                                   const MatrixXd& reconstruction,
                                   const ReferenceEntry& reference,
                                   bool symmetric) {
  FactorQualification result;
  const double matrix_norm = std::max(matrix_inf_norm(matrix), 1.0);
  result.reconstruction_relative_inf =
      matrix_inf_norm(matrix - reconstruction) / matrix_norm;
  const double threshold =
      64.0 * static_cast<double>(matrix.rows()) * kUnitRoundoff;
  if (!std::isfinite(result.reconstruction_relative_inf) ||
      result.reconstruction_relative_inf > threshold) {
    result.reason = "reconstruction gate failed";
    return result;
  }
  const MatrixXd rhs = manufactured_rhs(matrix, symmetric);
  static constexpr std::array<std::string_view, 3> families{
      "operational", "constraint", "dynamic-range"};
  for (Index family = 0; family < 3; ++family) {
    const auto& authority = reference.rhs[static_cast<std::size_t>(family)];
    if (authority.family != families[static_cast<std::size_t>(family)] ||
        sha256_vector(rhs.col(family)) != authority.rhs_sha256) {
      result.reason = "manufactured RHS identity differs";
      return result;
    }
    auto [solution, refinements] =
        refined_solve(matrix, decomposition, rhs.col(family), &authority);
    result.refinements += refinements;
    const double backward =
        reduced_backward_error(matrix, solution, rhs.col(family), true);
    result.maximum_backward_error =
        std::max(result.maximum_backward_error, backward);
    const auto judgment = judge_reference(authority, solution);
    if (backward > threshold || judgment.status != "PASS") {
      result.reason = "backward or repaired-reference solution gate failed";
      return result;
    }
    ++result.reference_passes;
  }
  result.pass = true;
  result.reason = "qualified run-scoped input";
  return result;
}

struct BlockFactor {
  std::string block_id;
  std::string workload_id;
  std::string role;
  int level{};
  int ordinal{};
  Index source_value_rows{};
  Index value_rows{};
  Index gradient_points{};
  Index polynomial_order{};
  std::vector<std::int64_t> value_indices;
  std::vector<std::int64_t> gradient_indices;
  std::vector<std::uint8_t> inner_value;
  std::vector<std::uint8_t> inner_gradient;
  MatrixXd q_top;
  MatrixXd qtaq;
  Eigen::LDLT<MatrixXd> qtaq_factor;
  MatrixXd a_top;
  MatrixXd p_top;
  Eigen::FullPivLU<MatrixXd> p_top_factor;
  FactorQualification qtaq_qualification;
  FactorQualification p_top_qualification;
  double maximum_dynamic_backward{};

  VectorXd gather(const VectorXd& residual) const {
    VectorXd local(value_rows + 3 * gradient_points);
    for (Index i = 0; i < value_rows; ++i) {
      local(i) = residual(value_indices[static_cast<std::size_t>(i)]);
    }
    for (Index i = 0; i < gradient_points; ++i) {
      const auto global = gradient_indices[static_cast<std::size_t>(i)];
      local.segment<3>(value_rows + 3 * i) =
          residual.segment<3>(source_value_rows + 3 * global);
    }
    return local;
  }

  VectorXd dynamic_projected_solve(const VectorXd& rhs) {
    VectorXd solution = qtaq_factor.solve(rhs);
    const double threshold =
        64.0 * static_cast<double>(qtaq.rows()) * kUnitRoundoff;
    double backward = reduced_backward_error(qtaq, solution, rhs, false);
    if (backward > threshold) {
      solution += qtaq_factor.solve(rhs - qtaq * solution);
      backward = reduced_backward_error(qtaq, solution, rhs, false);
    }
    maximum_dynamic_backward = std::max(maximum_dynamic_backward, backward);
    if (!solution.allFinite() || backward > threshold) {
      fail("dynamic projected factor solve failed backward gate: " + block_id);
    }
    return solution;
  }

  VectorXd dynamic_p_top_solve(const VectorXd& rhs) {
    VectorXd solution = p_top_factor.solve(rhs);
    const double threshold =
        64.0 * static_cast<double>(p_top.rows()) * kUnitRoundoff;
    double backward = reduced_backward_error(p_top, solution, rhs, false);
    if (backward > threshold) {
      solution += p_top_factor.solve(rhs - p_top * solution);
      backward = reduced_backward_error(p_top, solution, rhs, false);
    }
    maximum_dynamic_backward = std::max(maximum_dynamic_backward, backward);
    if (!solution.allFinite() || backward > threshold) {
      fail("dynamic P_top factor solve failed backward gate: " + block_id);
    }
    return solution;
  }

  VectorXd local_solution(const VectorXd& residual, VectorXd* polynomial) {
    const VectorXd values = gather(residual);
    const Index local_order = values.size();
    VectorXd lambda(local_order);
    if (polynomial_order > 0) {
      const Index reduced = local_order - polynomial_order;
      const VectorXd projected_rhs =
          q_top.transpose() * values.head(polynomial_order) +
          values.tail(reduced);
      const VectorXd gamma = dynamic_projected_solve(projected_rhs);
      lambda.head(polynomial_order) = q_top * gamma;
      lambda.tail(reduced) = gamma;
    } else {
      lambda = dynamic_projected_solve(values);
    }
    if (polynomial != nullptr && polynomial_order > 0) {
      *polynomial = dynamic_p_top_solve(
          values.head(polynomial_order) - a_top * lambda);
    }
    return lambda;
  }

  void scatter_fine(const VectorXd& lambda, VectorXd& result) const {
    for (Index i = 0; i < value_rows; ++i) {
      if (inner_value[static_cast<std::size_t>(i)] != 0) {
        result(value_indices[static_cast<std::size_t>(i)]) = lambda(i);
      }
    }
    for (Index i = 0; i < gradient_points; ++i) {
      if (inner_gradient[static_cast<std::size_t>(i)] != 0) {
        const auto global = gradient_indices[static_cast<std::size_t>(i)];
        result.segment<3>(source_value_rows + 3 * global) =
            lambda.segment<3>(value_rows + 3 * i);
      }
    }
  }

  void scatter_coarse(const VectorXd& lambda, const VectorXd& polynomial,
                      VectorXd& result) const {
    for (Index i = 0; i < value_rows; ++i) {
      result(value_indices[static_cast<std::size_t>(i)]) = lambda(i);
    }
    for (Index i = 0; i < gradient_points; ++i) {
      const auto global = gradient_indices[static_cast<std::size_t>(i)];
      result.segment<3>(source_value_rows + 3 * global) =
          lambda.segment<3>(value_rows + 3 * i);
    }
    if (polynomial_order > 0) {
      result.tail(polynomial_order) = polynomial;
    }
  }
};

polatory::Model<3> make_model(const pt::ptree& workload) {
  std::vector<polatory::rbf::Rbf<3>> rbfs;
  for (const auto& [unused, rbf_node] : workload.get_child("model.rbfs")) {
    static_cast<void>(unused);
    std::vector<double> parameters;
    for (const auto& [parameter_unused, value] :
         rbf_node.get_child("parameters.values")) {
      static_cast<void>(parameter_unused);
      parameters.push_back(value.get<double>("decimal"));
    }
    auto rbf = polatory::rbf::make_rbf<3>(
        rbf_node.get<std::string>("short_name"), parameters);
    polatory::Mat<3> anisotropy;
    std::size_t index = 0;
    for (const auto& [aniso_unused, value] :
         rbf_node.get_child("anisotropy.values")) {
      static_cast<void>(aniso_unused);
      anisotropy(static_cast<Index>(index / 3), static_cast<Index>(index % 3)) =
          value.get<double>("decimal");
      ++index;
    }
    if (index != 9) {
      fail("workload anisotropy shape differs");
    }
    rbf.set_anisotropy(anisotropy);
    rbfs.push_back(std::move(rbf));
  }
  polatory::Model<3> model(
      std::move(rbfs), workload.get<int>("resolved_polynomial_degree"));
  model.set_nugget(workload.get<double>("model.nugget.value.decimal"));
  return model;
}

std::set<std::string> wanted_factor_hashes(const Corpus& corpus,
                                           const std::string& workload_id) {
  std::set<std::string> result;
  std::unordered_map<std::string, std::string> factor_artifacts;
  for (const auto& [unused, source] : corpus.raw().get_child("factor_sources")) {
    static_cast<void>(unused);
    if (source.get<std::string>("workload_id") == workload_id) {
      factor_artifacts.emplace(source.get<std::string>("factor_source_id"),
                               source.get<std::string>("matrix_artifact"));
    }
  }
  for (const auto& [source_id, artifact_id] : factor_artifacts) {
    static_cast<void>(source_id);
    result.insert(corpus.artifact(artifact_id).sha256);
  }
  return result;
}

std::vector<BlockFactor> load_blocks(const Corpus& corpus,
                                     const std::string& workload_id,
                                     const ReferenceMap& references) {
  std::vector<BlockFactor> result;
  for (const auto& [unused, node] : corpus.raw().get_child("blocks")) {
    static_cast<void>(unused);
    if (node.get<std::string>("workload_id") != workload_id) {
      continue;
    }
    BlockFactor block;
    block.block_id = node.get<std::string>("block_id");
    block.workload_id = workload_id;
    block.role = node.get<std::string>("role");
    block.level = node.get<int>("level");
    block.ordinal = node.get<int>("ordinal");
    block.source_value_rows = node.get<Index>("source_value_rows");
    block.value_rows = node.get<Index>("value_rows");
    block.gradient_points = node.get<Index>("gradient_points");
    block.polynomial_order = node.get<Index>("polynomial_order");
    block.value_indices = corpus.read_vector<std::int64_t>(
        node.get<std::string>("artifacts.domain_value_indices"), "i64");
    block.gradient_indices = corpus.read_vector<std::int64_t>(
        node.get<std::string>("artifacts.domain_gradient_indices"), "i64");
    block.inner_value = corpus.read_vector<std::uint8_t>(
        node.get<std::string>("artifacts.inner_value_mask"), "u8");
    block.inner_gradient = corpus.read_vector<std::uint8_t>(
        node.get<std::string>("artifacts.inner_gradient_mask"), "u8");
    if (block.value_indices.size() != static_cast<std::size_t>(block.value_rows) ||
        block.gradient_indices.size() !=
            static_cast<std::size_t>(block.gradient_points) ||
        block.inner_value.size() != static_cast<std::size_t>(block.value_rows) ||
        block.inner_gradient.size() !=
            static_cast<std::size_t>(block.gradient_points)) {
      fail("block row-map/mask shape differs: " + block.block_id);
    }
    if (block.polynomial_order > 0) {
      block.q_top = corpus.read_row_matrix(
          node.get<std::string>("artifacts.q_top_row_major"));
    }
    const auto qtaq_id = node.get<std::string>("artifacts.qtaq_lower");
    const auto& qtaq_artifact = corpus.artifact(qtaq_id);
    block.qtaq = corpus.read_lower_matrix(qtaq_id);
    block.qtaq_factor.compute(block.qtaq);
    if (block.qtaq_factor.info() != Eigen::Success) {
      fail("run-scoped QTAQ factorization failed: " + block.block_id);
    }
    const auto qtaq_reference = references.find(qtaq_artifact.sha256);
    if (qtaq_reference == references.end()) {
      fail("run-scoped QTAQ reference missing: " + block.block_id);
    }
    block.qtaq_qualification = qualify_factor(
        block.qtaq, block.qtaq_factor,
        MatrixXd(block.qtaq_factor.reconstructedMatrix()), qtaq_reference->second,
        true);
    if (!block.qtaq_qualification.pass) {
      fail("run-scoped QTAQ input did not qualify: " + block.block_id + ": " +
           block.qtaq_qualification.reason);
    }
    if (block.role == "coarse" && block.polynomial_order > 0) {
      const auto p_top_id =
          node.get<std::string>("artifacts.p_top_row_major");
      const auto& p_top_artifact = corpus.artifact(p_top_id);
      block.p_top = corpus.read_row_matrix(p_top_id);
      block.p_top_factor.compute(block.p_top);
      if (!block.p_top_factor.isInvertible()) {
        fail("run-scoped P_top factorization failed: " + block.block_id);
      }
      const auto p_top_reference = references.find(p_top_artifact.sha256);
      if (p_top_reference == references.end()) {
        fail("run-scoped P_top reference missing: " + block.block_id);
      }
      block.p_top_qualification = qualify_factor(
          block.p_top, block.p_top_factor,
          MatrixXd(block.p_top_factor.reconstructedMatrix()),
          p_top_reference->second, false);
      if (!block.p_top_qualification.pass) {
        fail("run-scoped P_top input did not qualify: " + block.block_id + ": " +
             block.p_top_qualification.reason);
      }
      const auto a_lower_id = node.get<std::string>("artifacts.a_lower");
      const auto& a_item = corpus.artifact(a_lower_id);
      const auto packed = corpus.read_vector<double>(a_lower_id, "f64");
      const Index local_order =
          block.value_rows + 3 * block.gradient_points;
      block.a_top.resize(block.polynomial_order, local_order);
      for (Index row = 0; row < block.polynomial_order; ++row) {
        for (Index column = 0; column < local_order; ++column) {
          const Index high = std::max(row, column);
          const Index low = std::min(row, column);
          block.a_top(row, column) =
              packed[static_cast<std::size_t>(high * (high + 1) / 2 + low)];
        }
      }
      if (a_item.shape.size() != 2 ||
          a_item.shape[0] != static_cast<std::size_t>(local_order)) {
        fail("coarse A artifact shape differs");
      }
    }
    result.push_back(std::move(block));
  }
  std::sort(result.begin(), result.end(), [](const auto& left, const auto& right) {
    if (left.level != right.level) {
      return left.level < right.level;
    }
    return left.ordinal < right.ordinal;
  });
  return result;
}

enum class ActionKind { Solver, Preconditioner, Certificate };

struct ActionCounts {
  int solver{};
  int preconditioner{};
  int certificate{};
};

class WorkloadContext {
 public:
  WorkloadContext(const Corpus& corpus, const pt::ptree& descriptor,
                  const ReferenceMap& references)
      : workload_id_(descriptor.get<std::string>("workload_id")),
        scale_id_(descriptor.get<std::string>("scale_id")),
        value_rows_(descriptor.get<Index>("value_rows")),
        gradient_points_(descriptor.get<Index>("gradient_points")),
        scalar_order_(descriptor.get<Index>("scalar_order")),
        polynomial_order_(descriptor.get<Index>("polynomial_order")),
        model_(make_model(descriptor)),
        points_(corpus.read_row_matrix(
            descriptor.get<std::string>("artifacts.value_points"))),
        gradient_points_matrix_(corpus.read_row_matrix(
            descriptor.get<std::string>("artifacts.gradient_points"))),
        observations_(corpus.read_eigen_vector(
            descriptor.get<std::string>("artifacts.observations"))),
        blocks_(load_blocks(corpus, workload_id_, references)),
        polynomial_(
            polatory::polynomial::MonomialBasis<3>(model_.poly_degree())
                .evaluate(points_, gradient_points_matrix_)),
        operator_(model_, points_, gradient_points_matrix_, kOperatorAccuracy,
                  kOperatorAccuracy) {
    if (points_.rows() != value_rows_ || points_.cols() != 3 ||
        gradient_points_matrix_.rows() != gradient_points_ ||
        gradient_points_matrix_.cols() != 3 ||
        observations_.size() != scalar_order_ ||
        polynomial_.rows() != scalar_order_ ||
        polynomial_.cols() != polynomial_order_) {
      fail("workload payload shape differs: " + workload_id_);
    }
    rhs_ = VectorXd::Zero(size());
    rhs_.head(scalar_order_) = observations_;
    if (scale_id_ == "1k" || workload_id_ == "M3-HERMITE-10K") {
      direct_a_ =
          polatory::preconditioner::mat_a(model_, points_, gradient_points_matrix_);
    }
    orthonormal_polynomial_ = polynomial_;
    if (polynomial_order_ > 0) {
      polatory::common::orthonormalize_cols(orthonormal_polynomial_);
      ap_.resize(scalar_order_, polynomial_order_);
      for (Index column = 0; column < polynomial_order_; ++column) {
        VectorXd weights = VectorXd::Zero(size());
        weights.head(scalar_order_) = orthonormal_polynomial_.col(column);
        ap_.col(column) =
            apply(weights, ActionKind::Preconditioner).head(scalar_order_);
      }
    }
  }

  const std::string& workload_id() const { return workload_id_; }
  const std::string& scale_id() const { return scale_id_; }
  Index value_rows() const { return value_rows_; }
  Index gradient_points() const { return gradient_points_; }
  Index scalar_order() const { return scalar_order_; }
  Index polynomial_order() const { return polynomial_order_; }
  Index size() const { return scalar_order_ + polynomial_order_; }
  bool screening_action_is_authoritative() const {
    return direct_a_.has_value();
  }
  const VectorXd& rhs() const { return rhs_; }
  std::vector<BlockFactor>& blocks() { return blocks_; }
  const std::vector<BlockFactor>& blocks() const { return blocks_; }
  const MatrixXd& polynomial() const { return polynomial_; }
  const MatrixXd& orthonormal_polynomial() const {
    return orthonormal_polynomial_;
  }
  const MatrixXd& ap() const { return ap_; }
  const ActionCounts& counts() const { return counts_; }
  void reset_counts() { counts_ = {}; }

  VectorXd apply(const VectorXd& weights, ActionKind kind) {
    if (weights.size() != size()) {
      fail("operator input shape differs");
    }
    switch (kind) {
      case ActionKind::Solver:
        ++counts_.solver;
        break;
      case ActionKind::Preconditioner:
        ++counts_.preconditioner;
        if (counts_.preconditioner > kMaximumPreconditionerOperatorActions) {
          fail("preconditioner operator-action budget exhausted");
        }
        break;
      case ActionKind::Certificate:
        ++counts_.certificate;
        break;
    }
    if (direct_a_.has_value()) {
      VectorXd result = VectorXd::Zero(size());
      result.head(scalar_order_) =
          *direct_a_ * weights.head(scalar_order_);
      if (polynomial_order_ > 0) {
        result.head(scalar_order_) +=
            polynomial_ * weights.tail(polynomial_order_);
        result.tail(polynomial_order_) =
            polynomial_.transpose() * weights.head(scalar_order_);
      }
      return result;
    }
    return operator_(weights);
  }

  struct Certificate {
    bool pass{};
    double value_residual{};
    double gradient_residual{};
    double cpd_eta{};
  };

  Certificate certify_bound(const VectorXd& solution) {
    return certificate_from_action(solution,
                                   apply(solution, ActionKind::Certificate));
  }

  Certificate certify_direct(const VectorXd& solution) const {
    if (direct_a_.has_value()) {
      VectorXd action = VectorXd::Zero(size());
      action.head(scalar_order_) =
          *direct_a_ * solution.head(scalar_order_);
      if (polynomial_order_ > 0) {
        action.head(scalar_order_) +=
            polynomial_ * solution.tail(polynomial_order_);
        action.tail(polynomial_order_) =
            polynomial_.transpose() * solution.head(scalar_order_);
      }
      return certificate_from_action(solution, action);
    }
    polatory::interpolation::DirectEvaluator<3> direct(
        model_, points_, gradient_points_matrix_);
    direct.set_weights(solution);
    VectorXd fit = direct.evaluate(points_, gradient_points_matrix_);
    fit.head(value_rows_) +=
        solution.head(value_rows_) * model_.nugget();
    VectorXd action = VectorXd::Zero(size());
    action.head(scalar_order_) = fit;
    if (polynomial_order_ > 0) {
      action.tail(polynomial_order_) =
          polynomial_.transpose() * solution.head(scalar_order_);
    }
    return certificate_from_action(solution, action);
  }

 private:
  Certificate certificate_from_action(const VectorXd& solution,
                                      const VectorXd& action) const {
    const VectorXd residual = rhs_ - action;
    Certificate result;
    result.value_residual =
        value_rows_ == 0
            ? 0.0
            : residual.head(value_rows_).lpNorm<Eigen::Infinity>();
    result.gradient_residual =
        gradient_points_ == 0
            ? 0.0
            : residual.segment(value_rows_, 3 * gradient_points_)
                  .lpNorm<Eigen::Infinity>();
    if (polynomial_order_ > 0) {
      const double denominator =
          matrix_inf_norm(polynomial_.transpose()) *
          solution.head(scalar_order_).lpNorm<Eigen::Infinity>();
      const double numerator =
          action.tail(polynomial_order_).lpNorm<Eigen::Infinity>();
      result.cpd_eta =
          denominator == 0.0 ? (numerator == 0.0 ? 0.0
                                                : std::numeric_limits<double>::infinity())
                             : numerator / denominator;
    }
    result.pass = std::isfinite(result.value_residual) &&
                  std::isfinite(result.gradient_residual) &&
                  std::isfinite(result.cpd_eta) &&
                  result.value_residual <= kFitTolerance &&
                  result.gradient_residual <= kFitTolerance &&
                  result.cpd_eta <= kCpdTolerance;
    return result;
  }

  std::string workload_id_;
  std::string scale_id_;
  Index value_rows_{};
  Index gradient_points_{};
  Index scalar_order_{};
  Index polynomial_order_{};
  polatory::Model<3> model_;
  MatrixXd points_;
  MatrixXd gradient_points_matrix_;
  VectorXd observations_;
  VectorXd rhs_;
  std::vector<BlockFactor> blocks_;
  MatrixXd polynomial_;
  MatrixXd orthonormal_polynomial_;
  MatrixXd ap_;
  std::optional<MatrixXd> direct_a_;
  polatory::interpolation::Operator<3> operator_;
  ActionCounts counts_;
};

enum class Topology { OneLevel, Additive, Projected, FrozenResidualCorrection };

std::string topology_name(Topology topology) {
  switch (topology) {
    case Topology::OneLevel:
      return "one-level-ras";
    case Topology::Additive:
      return "same-hierarchy-additive-ras";
    case Topology::Projected:
      return "projected-deflated-ras";
    case Topology::FrozenResidualCorrection:
      return "frozen-residual-correction-ras";
  }
  fail("unknown topology");
}

struct PreconditionerCounts {
  int applications{};
  int local_solves{};
  int coarse_solves{};
};

class RasPreconditioner {
 public:
  explicit RasPreconditioner(WorkloadContext& workload) : workload_(workload) {
    for (auto& block : workload_.blocks()) {
      if (block.role == "coarse") {
        if (coarse_ != nullptr) {
          fail("workload has more than one coarse block");
        }
        coarse_ = &block;
      } else if (block.role == "fine") {
        fine_.push_back(&block);
      } else {
        fail("workload has unknown block role");
      }
    }
    if (coarse_ == nullptr) {
      fail("workload has no coarse block");
    }
  }

  void reset_counts() { counts_ = {}; }
  const PreconditionerCounts& counts() const { return counts_; }

  VectorXd apply(const VectorXd& input, Topology topology) {
    ++counts_.applications;
    VectorXd residual = input.head(workload_.scalar_order());
    if (fine_.empty()) {
      return coarse_solve(residual);
    }
    switch (topology) {
      case Topology::OneLevel: {
        VectorXd fine = fine_solve(residual);
        project_output(fine);
        return fine;
      }
      case Topology::Additive: {
        VectorXd fine = fine_solve(residual);
        project_output(fine);
        return fine + coarse_solve(residual);
      }
      case Topology::Projected: {
        VectorXd fine = fine_solve(residual);
        project_output(fine);
        residual -=
            workload_.apply(fine, ActionKind::Preconditioner)
                .head(workload_.scalar_order());
        return fine + coarse_solve(residual);
      }
      case Topology::FrozenResidualCorrection: {
        VectorXd total = coarse_solve(residual);
        residual -=
            workload_.apply(total, ActionKind::Preconditioner)
                .head(workload_.scalar_order());
        VectorXd fine = fine_solve(residual);
        total += fine;
        residual -=
            workload_.apply(fine, ActionKind::Preconditioner)
                .head(workload_.scalar_order());
        orthogonalize_with_residual(total, residual);
        total += coarse_solve(residual);
        return total;
      }
    }
    fail("unknown topology");
  }

 private:
  VectorXd fine_solve(const VectorXd& residual) {
    VectorXd result = VectorXd::Zero(workload_.size());
    for (auto* block : fine_) {
      const VectorXd local = block->local_solution(residual, nullptr);
      block->scatter_fine(local, result);
      ++counts_.local_solves;
    }
    return result;
  }

  VectorXd coarse_solve(const VectorXd& residual) {
    VectorXd result = VectorXd::Zero(workload_.size());
    VectorXd polynomial;
    const VectorXd local = coarse_->local_solution(
        residual, workload_.polynomial_order() > 0 ? &polynomial : nullptr);
    coarse_->scatter_coarse(local, polynomial, result);
    ++counts_.coarse_solves;
    return result;
  }

  void project_output(VectorXd& weights) const {
    if (workload_.polynomial_order() == 0) {
      return;
    }
    const VectorXd dot =
        workload_.orthonormal_polynomial().transpose() *
        weights.head(workload_.scalar_order());
    weights.head(workload_.scalar_order()) -=
        workload_.orthonormal_polynomial() * dot;
  }

  void orthogonalize_with_residual(VectorXd& weights,
                                   VectorXd& residual) const {
    if (workload_.polynomial_order() == 0) {
      return;
    }
    const VectorXd dot =
        workload_.orthonormal_polynomial().transpose() *
        weights.head(workload_.scalar_order());
    weights.head(workload_.scalar_order()) -=
        workload_.orthonormal_polynomial() * dot;
    residual += workload_.ap() * dot;
  }

  WorkloadContext& workload_;
  BlockFactor* coarse_{};
  std::vector<BlockFactor*> fine_;
  PreconditionerCounts counts_;
};

enum class Orthogonalization { ParityCgs, RobustMgsDgks };

std::string orthogonalization_name(Orthogonalization orthogonalization) {
  return orthogonalization == Orthogonalization::ParityCgs
             ? "parity-one-pass-cgs"
             : "robust-mgs-dgks";
}

struct RunResult {
  std::string workload_id;
  std::string scale_id;
  Topology topology{};
  Orthogonalization orthogonalization{};
  int window{};
  std::string status;
  int iterations{};
  int restarts{};
  int reorthogonalizations{};
  double maximum_orthogonality_defect{};
  double recurrence_residual{};
  WorkloadContext::Certificate bound_certificate;
  std::optional<WorkloadContext::Certificate> direct_certificate;
  ActionCounts actions;
  PreconditionerCounts preconditioner;
  std::uint64_t basis_bytes{};
  ProcessMemory memory;
  double elapsed_seconds{};
  VectorXd solution;
};

VectorXd triangular_candidate(const VectorXd& base,
                              const std::vector<VectorXd>& z,
                              const MatrixXd& hessenberg,
                              const VectorXd& g, int count) {
  VectorXd y(count);
  for (int row = count - 1; row >= 0; --row) {
    double value = g(row);
    for (int column = row + 1; column < count; ++column) {
      value -= hessenberg(row, column) * y(column);
    }
    if (hessenberg(row, row) == 0.0) {
      fail("FGMRES triangular factor is singular");
    }
    y(row) = value / hessenberg(row, row);
  }
  VectorXd candidate = base;
  for (int column = 0; column < count; ++column) {
    candidate += y(column) * z[static_cast<std::size_t>(column)];
  }
  return candidate;
}

double orthogonality_defect(const std::vector<VectorXd>& basis) {
  double result = 0.0;
  for (std::size_t i = 0; i < basis.size(); ++i) {
    result = std::max(result, std::abs(basis[i].squaredNorm() - 1.0));
    for (std::size_t j = 0; j < i; ++j) {
      result = std::max(result, std::abs(basis[i].dot(basis[j])));
    }
  }
  return result;
}

RunResult run_fgmres(WorkloadContext& workload, Topology topology, int window,
                     Orthogonalization orthogonalization) {
  const auto started = std::chrono::steady_clock::now();
  workload.reset_counts();
  RasPreconditioner preconditioner(workload);
  preconditioner.reset_counts();
  RunResult result;
  result.workload_id = workload.workload_id();
  result.scale_id = workload.scale_id();
  result.topology = topology;
  result.orthogonalization = orthogonalization;
  result.window = window;
  VectorXd x = VectorXd::Zero(workload.size());
  VectorXd residual = workload.rhs();
  result.bound_certificate = workload.certify_bound(x);
  const double trigger =
      std::sqrt(static_cast<double>(workload.size())) * kFitTolerance;
  const auto passing_status = [&] {
    return workload.screening_action_is_authoritative()
               ? "MECHANISM_CERTIFIED"
               : "SCREEN_PASSED";
  };

  while (result.iterations < kMaximumIterations) {
    const double beta = residual.norm();
    if (!std::isfinite(beta)) {
      result.status = "NUMERICAL_BREAKDOWN";
      break;
    }
    if (beta == 0.0) {
      result.bound_certificate = workload.certify_bound(x);
      result.status = result.bound_certificate.pass ? passing_status()
                                                    : "FALSE_RECURRENCE_SUCCESS";
      break;
    }
    const int cycle_limit =
        std::min(window, kMaximumIterations - result.iterations);
    std::vector<VectorXd> v;
    std::vector<VectorXd> z;
    v.reserve(static_cast<std::size_t>(cycle_limit + 1));
    z.reserve(static_cast<std::size_t>(cycle_limit));
    v.push_back(residual / beta);
    MatrixXd h = MatrixXd::Zero(cycle_limit + 1, cycle_limit);
    VectorXd cosines = VectorXd::Zero(cycle_limit);
    VectorXd sines = VectorXd::Zero(cycle_limit);
    VectorXd g = VectorXd::Zero(cycle_limit + 1);
    g(0) = beta;
    bool left_cycle = false;

    for (int column = 0; column < cycle_limit; ++column) {
      VectorXd preconditioned =
          preconditioner.apply(v[static_cast<std::size_t>(column)], topology);
      z.push_back(preconditioned);
      VectorXd w = workload.apply(preconditioned, ActionKind::Solver);
      const double before = w.norm();
      if (orthogonalization == Orthogonalization::ParityCgs) {
        VectorXd coefficients(column + 1);
        for (int row = 0; row <= column; ++row) {
          coefficients(row) = v[static_cast<std::size_t>(row)].dot(w);
          h(row, column) = coefficients(row);
        }
        for (int row = 0; row <= column; ++row) {
          w -= coefficients(row) * v[static_cast<std::size_t>(row)];
        }
      } else {
        for (int row = 0; row <= column; ++row) {
          const double coefficient =
              v[static_cast<std::size_t>(row)].dot(w);
          h(row, column) += coefficient;
          w -= coefficient * v[static_cast<std::size_t>(row)];
        }
        const double after_first = w.norm();
        if (after_first < 0.717 * before) {
          ++result.reorthogonalizations;
          for (int row = 0; row <= column; ++row) {
            const double coefficient =
                v[static_cast<std::size_t>(row)].dot(w);
            h(row, column) += coefficient;
            w -= coefficient * v[static_cast<std::size_t>(row)];
          }
        }
      }
      h(column + 1, column) = w.norm();
      const bool happy_breakdown =
          h(column + 1, column) <=
          32.0 * kMachineEpsilon * std::max(before, 1.0);
      if (!happy_breakdown) {
        v.push_back(w / h(column + 1, column));
      }

      for (int row = 0; row < column; ++row) {
        const double top = h(row, column);
        const double bottom = h(row + 1, column);
        h(row, column) = cosines(row) * top + sines(row) * bottom;
        h(row + 1, column) = -sines(row) * top + cosines(row) * bottom;
      }
      const double denominator =
          std::hypot(h(column, column), h(column + 1, column));
      if (denominator == 0.0 || !std::isfinite(denominator)) {
        result.status = "NUMERICAL_BREAKDOWN";
        left_cycle = true;
        break;
      }
      cosines(column) = h(column, column) / denominator;
      sines(column) = h(column + 1, column) / denominator;
      h(column, column) = denominator;
      h(column + 1, column) = 0.0;
      g(column + 1) = -sines(column) * g(column);
      g(column) = cosines(column) * g(column);
      ++result.iterations;
      result.recurrence_residual = std::abs(g(column + 1));

      const bool every_iteration = workload.scale_id() == "1k";
      const bool boundary = column + 1 == cycle_limit || happy_breakdown;
      const bool triggered = result.recurrence_residual <= trigger;
      if (every_iteration || boundary || triggered) {
        VectorXd candidate =
            triangular_candidate(x, z, h, g, column + 1);
        const auto certificate = workload.certify_bound(candidate);
        if (certificate.pass) {
          x = std::move(candidate);
          result.bound_certificate = certificate;
          result.status = passing_status();
          left_cycle = true;
          break;
        }
        if (happy_breakdown) {
          x = std::move(candidate);
          result.bound_certificate = certificate;
          result.status = "FALSE_RECURRENCE_SUCCESS";
          left_cycle = true;
          break;
        }
      }
    }

    result.maximum_orthogonality_defect =
        std::max(result.maximum_orthogonality_defect,
                 orthogonality_defect(v));
    if (left_cycle) {
      break;
    }
    const int completed = static_cast<int>(z.size());
    x = triangular_candidate(x, z, h, g, completed);
    residual =
        workload.rhs() - workload.apply(x, ActionKind::Certificate);
    result.bound_certificate = workload.certify_bound(x);
    ++result.restarts;
    if (result.bound_certificate.pass) {
      result.status = passing_status();
      break;
    }
  }

  if (result.status.empty()) {
    result.status = "WORK_BUDGET_EXHAUSTED";
    result.bound_certificate = workload.certify_bound(x);
  }
  result.solution = x;
  result.actions = workload.counts();
  result.preconditioner = preconditioner.counts();
  result.basis_bytes =
      static_cast<std::uint64_t>(sizeof(double)) *
      static_cast<std::uint64_t>(workload.size()) *
      static_cast<std::uint64_t>(2 * window + 1);
  result.memory = process_memory();
  result.elapsed_seconds =
      std::chrono::duration<double>(std::chrono::steady_clock::now() - started)
          .count();
  return result;
}

struct ConfigurationScore {
  Topology topology{};
  int window{};
  int screened{};
  int total_iterations{};
  int total_actions{};
  std::uint64_t basis_bytes{};
};

struct FactorEvidence {
  int qualified_factor_sources{};
  int repaired_reference_rhs_passes{};
  int qualification_refinements{};
  double maximum_reconstruction_relative_inf{};
  double maximum_qualification_backward_error{};
  double maximum_dynamic_backward_error{};

  void add(const FactorQualification& qualification) {
    if (!qualification.pass) {
      fail("unqualified factor reached evidence aggregation");
    }
    ++qualified_factor_sources;
    repaired_reference_rhs_passes += qualification.reference_passes;
    qualification_refinements += qualification.refinements;
    maximum_reconstruction_relative_inf =
        std::max(maximum_reconstruction_relative_inf,
                 qualification.reconstruction_relative_inf);
    maximum_qualification_backward_error =
        std::max(maximum_qualification_backward_error,
                 qualification.maximum_backward_error);
  }

  void add(const WorkloadContext& workload) {
    for (const auto& block : workload.blocks()) {
      add(block.qtaq_qualification);
      if (block.p_top.size() != 0) {
        add(block.p_top_qualification);
      }
      maximum_dynamic_backward_error =
          std::max(maximum_dynamic_backward_error,
                   block.maximum_dynamic_backward);
    }
  }
};

std::vector<ConfigurationScore> score_configurations(
    const std::vector<RunResult>& results,
    const std::set<std::string>& ten_k_workloads) {
  std::map<std::pair<Topology, int>, ConfigurationScore> scores;
  for (const auto& result : results) {
    if (result.scale_id != "10k" ||
        result.orthogonalization != Orthogonalization::RobustMgsDgks) {
      continue;
    }
    auto& score = scores[{result.topology, result.window}];
    score.topology = result.topology;
    score.window = result.window;
    if (result.status == "SCREEN_PASSED" ||
        result.status == "MECHANISM_CERTIFIED") {
      ++score.screened;
    }
    score.total_iterations += result.iterations;
    score.total_actions += result.actions.solver + result.actions.preconditioner +
                           result.actions.certificate;
    score.basis_bytes = std::max(score.basis_bytes, result.basis_bytes);
  }
  std::vector<ConfigurationScore> result;
  for (const auto& [unused, score] : scores) {
    static_cast<void>(unused);
    result.push_back(score);
  }
  std::sort(result.begin(), result.end(), [&](const auto& left, const auto& right) {
    const bool left_complete =
        left.screened == static_cast<int>(ten_k_workloads.size());
    const bool right_complete =
        right.screened == static_cast<int>(ten_k_workloads.size());
    if (left_complete != right_complete) {
      return left_complete > right_complete;
    }
    if (left.screened != right.screened) {
      return left.screened > right.screened;
    }
    if (left.total_actions != right.total_actions) {
      return left.total_actions < right.total_actions;
    }
    if (left.basis_bytes != right.basis_bytes) {
      return left.basis_bytes < right.basis_bytes;
    }
    return topology_name(left.topology) < topology_name(right.topology);
  });
  return result;
}

void write_results(const fs::path& path, const std::vector<RunResult>& results,
                   const std::vector<ConfigurationScore>& scores,
                   const std::vector<ConfigurationScore>& finalists,
                   const FactorEvidence& factor_evidence,
                   std::size_t unique_factor_payloads,
                   std::string_view disposition) {
  fs::create_directories(path.parent_path());
  const auto temporary = path.string() + ".tmp";
  std::ofstream out(temporary, std::ios::binary | std::ios::trunc);
  if (!out) {
    fail("cannot create panel result");
  }
  out << std::setprecision(17);
  out << "{\n";
  out << "  \"schema\": \"RapidRBF/FgmresRasMechanismPanel/v1\",\n";
  out << "  \"prototype_disposition\": \"" << disposition << "\",\n";
  out << "  \"authority\": {\n";
  out << "    \"canonical_corpus_sha256\": \"" << kCorpusDigest << "\",\n";
  out << "    \"reference_manifest_sha256\": \"" << kReferenceManifestSha
      << "\",\n";
  out << "    \"factor_backend_release_admitted\": false,\n";
  out << "    \"operator_routes\": {\n";
  out << "      \"1k\": \"complete-direct-matrix-action\",\n";
  out << "      \"M3-HERMITE-10K\": \"complete-direct-matrix-action\",\n";
  out << "      \"other_10k\": "
         "\"frozen-polatory-zero-request-screening-action\"\n";
  out << "    },\n";
  out << "    \"formal_fit_acceptance_claimed\": false\n";
  out << "  },\n";
  out << "  \"run_scoped_factor_evidence\": {\n";
  out << "    \"release_admission_claimed\": false,\n";
  out << "    \"unique_matrix_payloads\": " << unique_factor_payloads << ",\n";
  out << "    \"qualified_factor_sources\": "
      << factor_evidence.qualified_factor_sources << ",\n";
  out << "    \"repaired_reference_rhs_passes\": "
      << factor_evidence.repaired_reference_rhs_passes << ",\n";
  out << "    \"qualification_refinements\": "
      << factor_evidence.qualification_refinements << ",\n";
  out << "    \"maximum_reconstruction_relative_inf\": "
      << factor_evidence.maximum_reconstruction_relative_inf << ",\n";
  out << "    \"maximum_qualification_backward_error\": "
      << factor_evidence.maximum_qualification_backward_error << ",\n";
  out << "    \"maximum_dynamic_backward_error\": "
      << factor_evidence.maximum_dynamic_backward_error << "\n";
  out << "  },\n";
  out << "  \"frozen_profile\": {\n";
  out << "    \"fit_tolerance_hex\": \"0x1p-24\",\n";
  out << "    \"screening_operator_mode\": "
         "\"frozen-polatory-zero-request-order12-d8\",\n";
  out << "    \"cpd_eta_max\": \"2^-32\",\n";
  out << "    \"maximum_iterations\": " << kMaximumIterations << ",\n";
  out << "    \"maximum_preconditioner_operator_actions\": "
      << kMaximumPreconditionerOperatorActions << ",\n";
  out << "    \"openmp_threads\": 8,\n";
  out << "    \"mkl_threads\": 1,\n";
  out << "    \"windows\": [5, 32, 64]\n";
  out << "  },\n";
  out << "  \"runs\": [\n";
  for (std::size_t i = 0; i < results.size(); ++i) {
    const auto& run = results[i];
    out << "    {\n";
    out << "      \"workload_id\": \"" << json_escape(run.workload_id) << "\",\n";
    out << "      \"scale_id\": \"" << run.scale_id << "\",\n";
    out << "      \"topology\": \"" << topology_name(run.topology) << "\",\n";
    out << "      \"orthogonalization\": \""
        << orthogonalization_name(run.orthogonalization) << "\",\n";
    out << "      \"window\": " << run.window << ",\n";
    out << "      \"status\": \"" << run.status << "\",\n";
    out << "      \"iterations\": " << run.iterations << ",\n";
    out << "      \"restarts\": " << run.restarts << ",\n";
    out << "      \"reorthogonalizations\": " << run.reorthogonalizations << ",\n";
    out << "      \"maximum_orthogonality_defect\": "
        << run.maximum_orthogonality_defect << ",\n";
    out << "      \"recurrence_residual\": " << run.recurrence_residual << ",\n";
    out << "      \"bound_certificate\": {\"pass\": "
        << (run.bound_certificate.pass ? "true" : "false")
        << ", \"value_residual\": " << run.bound_certificate.value_residual
        << ", \"gradient_residual\": "
        << run.bound_certificate.gradient_residual << ", \"cpd_eta\": "
        << run.bound_certificate.cpd_eta << "},\n";
    if (run.direct_certificate.has_value()) {
      out << "      \"direct_certificate\": {\"pass\": "
          << (run.direct_certificate->pass ? "true" : "false")
          << ", \"value_residual\": " << run.direct_certificate->value_residual
          << ", \"gradient_residual\": "
          << run.direct_certificate->gradient_residual << ", \"cpd_eta\": "
          << run.direct_certificate->cpd_eta << "},\n";
    } else {
      out << "      \"direct_certificate\": null,\n";
    }
    out << "      \"actions\": {\"solver\": " << run.actions.solver
        << ", \"preconditioner_internal\": " << run.actions.preconditioner
        << ", \"certificate\": " << run.actions.certificate << "},\n";
    out << "      \"preconditioner\": {\"applications\": "
        << run.preconditioner.applications << ", \"local_solves\": "
        << run.preconditioner.local_solves << ", \"coarse_solves\": "
        << run.preconditioner.coarse_solves << "},\n";
    out << "      \"basis_bytes\": " << run.basis_bytes << ",\n";
    out << "      \"current_working_set_bytes\": "
        << run.memory.current_working_set_bytes << ",\n";
    out << "      \"process_peak_working_set_bytes\": "
        << run.memory.peak_working_set_bytes << ",\n";
    out << "      \"elapsed_seconds\": " << run.elapsed_seconds << "\n";
    out << "    }" << (i + 1 == results.size() ? "\n" : ",\n");
  }
  out << "  ],\n";
  const auto write_scores = [&](std::string_view name,
                                const std::vector<ConfigurationScore>& list) {
    out << "  \"" << name << "\": [\n";
    for (std::size_t i = 0; i < list.size(); ++i) {
      const auto& score = list[i];
      out << "    {\"topology\": \"" << topology_name(score.topology)
          << "\", \"window\": " << score.window
          << ", \"screened_10k\": " << score.screened
          << ", \"total_iterations\": " << score.total_iterations
          << ", \"total_actions\": " << score.total_actions
          << ", \"maximum_basis_bytes\": " << score.basis_bytes << "}"
          << (i + 1 == list.size() ? "\n" : ",\n");
    }
    out << "  ]";
  };
  write_scores("configuration_scores", scores);
  out << ",\n";
  write_scores("finalists", finalists);
  out << "\n}\n";
  out.close();
  if (!out) {
    fail("cannot finish panel result");
  }
  if (fs::exists(path)) {
    fail("panel result path must be fresh: " + path.string());
  }
  fs::rename(temporary, path);
}

struct Arguments {
  fs::path corpus;
  fs::path reference;
  fs::path output;
  std::optional<std::string> workload;
  bool quick{};
  bool audit_only{};
};

Arguments parse_arguments(int argc, char** argv) {
  Arguments result;
  for (int i = 1; i < argc; ++i) {
    const std::string argument = argv[i];
    const auto take = [&](std::string_view name) -> std::string {
      if (i + 1 >= argc) {
        fail("missing value for " + std::string(name));
      }
      return argv[++i];
    };
    if (argument == "--corpus") {
      result.corpus = take(argument);
    } else if (argument == "--reference") {
      result.reference = take(argument);
    } else if (argument == "--output") {
      result.output = take(argument);
    } else if (argument == "--workload") {
      result.workload = take(argument);
    } else if (argument == "--quick") {
      result.quick = true;
    } else if (argument == "--audit-only") {
      result.audit_only = true;
    } else {
      fail("unknown argument: " + argument);
    }
  }
  if (result.corpus.empty() || result.reference.empty() || result.output.empty()) {
    fail("--corpus, --reference, and --output are required");
  }
  return result;
}

int main(int argc, char** argv) {
  try {
    std::cout << std::unitbuf;
    omp_set_dynamic(0);
    omp_set_num_threads(8);
    mkl_set_dynamic(0);
    mkl_set_num_threads(1);
    const auto arguments = parse_arguments(argc, argv);
    std::cout << "RapidRBF Issue 32 throwaway mechanism panel\n";
    std::cout << "  fit tolerance: 0x1p-24; screening operator: "
                 "frozen Polatory zero-request (order=12,d=8)\n";
    std::cout << "  factor authority: repaired frozen-system reference\n";
    Corpus corpus(arguments.corpus);
    std::vector<pt::ptree> descriptors;
    for (const auto& [unused, descriptor] :
         corpus.raw().get_child("workloads")) {
      static_cast<void>(unused);
      const auto id = descriptor.get<std::string>("workload_id");
      if (!arguments.workload.has_value() || id == *arguments.workload) {
        descriptors.push_back(descriptor);
      }
    }
    if (descriptors.empty()) {
      fail("no selected workload exists");
    }

    std::vector<RunResult> results;
    FactorEvidence factor_evidence;
    std::set<std::string> ten_k_workloads;
    static constexpr std::array<Topology, 4> topologies{
        Topology::OneLevel, Topology::Additive, Topology::Projected,
        Topology::FrozenResidualCorrection};

    std::set<std::string> all_factor_hashes;
    for (const auto& descriptor : descriptors) {
      if (arguments.audit_only &&
          descriptor.get<std::string>("scale_id") != "10k") {
        continue;
      }
      const auto workload_hashes = wanted_factor_hashes(
          corpus, descriptor.get<std::string>("workload_id"));
      all_factor_hashes.insert(workload_hashes.begin(), workload_hashes.end());
    }
    const auto references =
        load_references(arguments.reference, all_factor_hashes);

    if (arguments.audit_only) {
      static constexpr std::array<std::pair<Topology, int>, 2>
          diagnostic_candidates{{
              {Topology::Projected, 64},
              {Topology::FrozenResidualCorrection, 64},
          }};
      for (const auto& descriptor : descriptors) {
        if (descriptor.get<std::string>("scale_id") != "10k") {
          continue;
        }
        const auto workload_id = descriptor.get<std::string>("workload_id");
        std::cout << "\n[" << workload_id
                  << "] diagnostic robust/parity direct audit...\n";
        WorkloadContext workload(corpus, descriptor, references);
        ten_k_workloads.insert(workload_id);
        for (const auto& [topology, window] : diagnostic_candidates) {
          for (const auto orthogonalization :
               {Orthogonalization::RobustMgsDgks,
                Orthogonalization::ParityCgs}) {
            std::cout << "  " << topology_name(topology) << " m=" << window
                      << " "
                      << orthogonalization_name(orthogonalization) << " ... "
                      << std::flush;
            auto run =
                run_fgmres(workload, topology, window, orthogonalization);
            run.direct_certificate = workload.certify_direct(run.solution);
            if (run.direct_certificate->pass) {
              run.status = "MECHANISM_CERTIFIED";
            } else if (run.status == "SCREEN_PASSED" ||
                       run.status == "MECHANISM_CERTIFIED") {
              run.status = "DIRECT_CERTIFICATE_FAILED";
            }
            std::cout << run.status << " iter=" << run.iterations
                      << " screen[value=" << std::scientific
                      << run.bound_certificate.value_residual << ",grad="
                      << run.bound_certificate.gradient_residual << "] direct["
                      << (run.direct_certificate->pass ? "PASS" : "FAIL")
                      << ",value=" << run.direct_certificate->value_residual
                      << ",grad="
                      << run.direct_certificate->gradient_residual << "]"
                      << std::defaultfloat << "\n";
            results.push_back(std::move(run));
          }
        }
        factor_evidence.add(workload);
      }
      std::vector<ConfigurationScore> diagnostic;
      for (const auto& [topology, window] : diagnostic_candidates) {
        ConfigurationScore score;
        score.topology = topology;
        score.window = window;
        diagnostic.push_back(score);
      }
      write_results(arguments.output, results, {}, diagnostic,
                    factor_evidence, all_factor_hashes.size(),
                    "DIAGNOSTIC_ORTHOGONALIZATION_DIRECT_AUDIT");
      std::cout << "\nresult: " << arguments.output << "\n";
      std::cout
          << "disposition: DIAGNOSTIC_ORTHOGONALIZATION_DIRECT_AUDIT\n";
      return 0;
    }

    for (const auto& descriptor : descriptors) {
      const auto workload_id = descriptor.get<std::string>("workload_id");
      const auto factor_hashes = wanted_factor_hashes(corpus, workload_id);
      std::cout << "\n[" << workload_id << "] loading and qualifying "
                << factor_hashes.size() << " run-scoped factor inputs...\n";
      WorkloadContext workload(corpus, descriptor, references);
      if (workload.scale_id() == "10k") {
        ten_k_workloads.insert(workload_id);
      }

      const auto run_and_report = [&](Topology topology, int window,
                                      Orthogonalization orthogonalization) {
        std::cout << "  " << topology_name(topology) << " m=" << window << " "
                  << orthogonalization_name(orthogonalization) << " ... "
                  << std::flush;
        auto result =
            run_fgmres(workload, topology, window, orthogonalization);
        std::cout << result.status << " iter=" << result.iterations
                  << " value=" << std::scientific
                  << result.bound_certificate.value_residual << " grad="
                  << result.bound_certificate.gradient_residual << " cpd="
                  << result.bound_certificate.cpd_eta << std::defaultfloat
                  << " time=" << result.elapsed_seconds << "s\n";
        results.push_back(std::move(result));
      };

      if (arguments.quick) {
        run_and_report(Topology::FrozenResidualCorrection, 32,
                       Orthogonalization::RobustMgsDgks);
      } else if (workload.scale_id() == "1k") {
        for (const auto topology : topologies) {
          for (const int window : kWindows) {
            run_and_report(topology, window,
                           Orthogonalization::RobustMgsDgks);
            run_and_report(topology, window,
                           Orthogonalization::ParityCgs);
          }
        }
      } else {
        for (const auto topology : topologies) {
          for (const int window : kWindows) {
            run_and_report(topology, window,
                           Orthogonalization::RobustMgsDgks);
          }
        }
      }
      factor_evidence.add(workload);
    }

    auto scores = score_configurations(results, ten_k_workloads);
    std::vector<ConfigurationScore> finalists;
    if (!arguments.quick && !ten_k_workloads.empty()) {
      for (const auto& score : scores) {
        if (score.screened != static_cast<int>(ten_k_workloads.size())) {
          continue;
        }
        if (finalists.empty() ||
            score.topology != finalists.front().topology) {
          finalists.push_back(score);
        }
        if (finalists.size() == 2) {
          break;
        }
      }

      const auto finalist_matches = [&](const RunResult& run) {
        return std::any_of(
            finalists.begin(), finalists.end(), [&](const auto& candidate) {
              return run.topology == candidate.topology &&
                     run.window == candidate.window;
            });
      };
      const bool one_k_trajectory_difference = std::any_of(
          results.begin(), results.end(), [&](const auto& robust) {
            if (robust.scale_id != "1k" ||
                robust.orthogonalization !=
                    Orthogonalization::RobustMgsDgks ||
                !finalist_matches(robust)) {
              return false;
            }
            const auto parity = std::find_if(
                results.begin(), results.end(), [&](const auto& candidate) {
                  return candidate.workload_id == robust.workload_id &&
                         candidate.topology == robust.topology &&
                         candidate.window == robust.window &&
                         candidate.orthogonalization ==
                             Orthogonalization::ParityCgs;
                });
            return parity == results.end() ||
                   robust.reorthogonalizations != 0 ||
                   robust.status != parity->status ||
                   robust.iterations != parity->iterations ||
                   robust.restarts != parity->restarts ||
                   robust.bound_certificate.pass !=
                       parity->bound_certificate.pass;
          });

      for (const auto& descriptor : descriptors) {
        if (descriptor.get<std::string>("scale_id") != "10k") {
          continue;
        }
        const auto workload_id = descriptor.get<std::string>("workload_id");
        std::cout << "\n[" << workload_id
                  << "] finalist parity trigger/direct audits...\n";
        WorkloadContext audit_workload(corpus, descriptor, references);
        for (const auto& finalist : finalists) {
          const auto robust = std::find_if(
              results.begin(), results.end(), [&](const auto& candidate) {
                return candidate.workload_id == workload_id &&
                       candidate.topology == finalist.topology &&
                       candidate.window == finalist.window &&
                       candidate.orthogonalization ==
                           Orthogonalization::RobustMgsDgks;
              });
          if (robust == results.end()) {
            fail("selected finalist has no robust 10k run");
          }
          if (one_k_trajectory_difference ||
              robust->reorthogonalizations != 0 ||
              (robust->status != "SCREEN_PASSED" &&
               robust->status != "MECHANISM_CERTIFIED")) {
            std::cout << "  parity rerun: "
                      << topology_name(finalist.topology) << " m="
                      << finalist.window << " ... " << std::flush;
            auto parity =
                run_fgmres(audit_workload, finalist.topology,
                           finalist.window, Orthogonalization::ParityCgs);
            std::cout << parity.status << " iter=" << parity.iterations
                      << " value=" << std::scientific
                      << parity.bound_certificate.value_residual << " grad="
                      << parity.bound_certificate.gradient_residual << " cpd="
                      << parity.bound_certificate.cpd_eta << std::defaultfloat
                      << "\n";
            results.push_back(std::move(parity));
          }
        }
        for (auto& run : results) {
          if (run.workload_id != workload_id || !finalist_matches(run) ||
              (run.status != "SCREEN_PASSED" &&
               run.status != "MECHANISM_CERTIFIED")) {
            continue;
          }
          std::cout << "  direct finalist audit: "
                    << topology_name(run.topology) << " m=" << run.window << " "
                    << orthogonalization_name(run.orthogonalization) << " ... "
                    << std::flush;
          run.direct_certificate =
              audit_workload.certify_direct(run.solution);
          run.status = run.direct_certificate->pass
                           ? "MECHANISM_CERTIFIED"
                           : "DIRECT_CERTIFICATE_FAILED";
          std::cout << (run.direct_certificate->pass ? "PASS" : "FAIL")
                    << " value=" << std::scientific
                    << run.direct_certificate->value_residual << " grad="
                    << run.direct_certificate->gradient_residual << " cpd="
                    << run.direct_certificate->cpd_eta << std::defaultfloat
                    << "\n";
        }
      }
    }

    bool all_finalists_direct = !finalists.empty();
    for (const auto& finalist : finalists) {
      for (const auto& workload_id : ten_k_workloads) {
        const auto run = std::find_if(results.begin(), results.end(),
                                      [&](const auto& item) {
          return item.workload_id == workload_id &&
                 item.topology == finalist.topology &&
                 item.window == finalist.window &&
                 item.orthogonalization ==
                     Orthogonalization::RobustMgsDgks;
        });
        if (run == results.end() || !run->direct_certificate.has_value() ||
            !run->direct_certificate->pass) {
          all_finalists_direct = false;
        }
      }
    }
    const std::string disposition =
        arguments.quick
            ? "DEVELOPMENT_SNAPSHOT"
            : (all_finalists_direct
                   ? "READY_FOR_LIVE_REVIEW"
                   : "NO_DIRECTLY_CERTIFIED_GLOBAL_FINALIST");
    write_results(arguments.output, results, scores, finalists,
                  factor_evidence, all_factor_hashes.size(), disposition);
    std::cout << "\nresult: " << arguments.output << "\n";
    std::cout << "disposition: " << disposition << "\n";
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "error: " << error.what() << "\n";
    return 2;
  }
}
