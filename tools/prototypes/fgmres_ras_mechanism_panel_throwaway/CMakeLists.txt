cmake_minimum_required(VERSION 3.25)

project(rapidrbf_fgmres_ras_mechanism_panel_throwaway LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

set(POLATORY_SOURCE "" CACHE PATH "Frozen Polatory source root")
set(POLATORY_BUILD "" CACHE PATH "Frozen Polatory build root")
set(BOOST_MULTIPRECISION_INCLUDE "" CACHE PATH
    "Prototype-local Boost.Multiprecision include root")
if(NOT EXISTS "${POLATORY_SOURCE}/include/polatory/model.hpp")
  message(FATAL_ERROR "POLATORY_SOURCE must name the frozen Polatory checkout")
endif()
if(NOT EXISTS "${POLATORY_BUILD}/src/polatory.lib")
  message(FATAL_ERROR "POLATORY_BUILD must name the matching frozen Polatory build")
endif()
if(NOT EXISTS "${BOOST_MULTIPRECISION_INCLUDE}/boost/multiprecision/cpp_int.hpp")
  message(FATAL_ERROR
          "BOOST_MULTIPRECISION_INCLUDE must contain boost/multiprecision/cpp_int.hpp")
endif()

find_package(Boost REQUIRED COMPONENTS filesystem)
find_package(Ceres CONFIG REQUIRED)
find_package(Eigen3 CONFIG REQUIRED)
find_package(FastFloat CONFIG REQUIRED)
find_package(flann CONFIG REQUIRED)
set(MKL_ARCH "intel64")
set(MKL_LINK "dynamic")
set(MKL_INTERFACE "lp64")
set(MKL_THREADING "sequential")
find_package(MKL CONFIG REQUIRED)
find_package(OpenMP REQUIRED)

add_library(polatory_frozen STATIC IMPORTED GLOBAL)
set_target_properties(polatory_frozen PROPERTIES
  IMPORTED_LOCATION "${POLATORY_BUILD}/src/polatory.lib"
)

add_executable(rapidrbf-fgmres-ras-panel
  src/main.cpp
)

target_compile_definitions(rapidrbf-fgmres-ras-panel PRIVATE
  EIGEN_DONT_PARALLELIZE
  EIGEN_MPL2_ONLY
  EIGEN_USE_BLAS
  WIN32_LEAN_AND_MEAN
  NOMINMAX
)
target_compile_options(rapidrbf-fgmres-ras-panel PRIVATE
  /W4
  /WX
  /wd4702
  -Wno-unused-command-line-argument
  -Wno-unused-parameter
)
target_include_directories(rapidrbf-fgmres-ras-panel PRIVATE
  "${BOOST_MULTIPRECISION_INCLUDE}"
  "${POLATORY_SOURCE}/include"
  "${POLATORY_BUILD}/scalfmm/install/include"
  "${POLATORY_BUILD}/vcpkg_installed/x64-windows/include/fftw"
)
target_link_libraries(rapidrbf-fgmres-ras-panel PRIVATE
  polatory_frozen
  Boost::boost
  Boost::filesystem
  ceres
  Eigen3::Eigen
  FastFloat::fast_float
  flann::flann_cpp
  MKL::MKL
  OpenMP::OpenMP_CXX
  bcrypt
  psapi
)
