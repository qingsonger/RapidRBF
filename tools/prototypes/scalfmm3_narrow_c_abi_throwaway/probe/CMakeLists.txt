cmake_minimum_required(VERSION 3.25)
project(rapidrbf_scalfmm_probe LANGUAGES C CXX)

if(NOT DEFINED POLATORY_ROOT)
  set(POLATORY_ROOT "D:/CODE/polatory")
endif()
cmake_path(ABSOLUTE_PATH POLATORY_ROOT NORMALIZE)

set(POLATORY_BUILD "${POLATORY_ROOT}/build")
set(POLATORY_TRIPLET "${POLATORY_BUILD}/vcpkg_installed/x64-windows")
set(POLATORY_LIBRARY "${POLATORY_BUILD}/src/polatory.lib")
set(SCALFMM_INCLUDE "${POLATORY_BUILD}/scalfmm/install/include")
set(LIBOMP_LIBRARY
    "C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Tools/MSVC/14.44.35207/lib/x64/libomp.lib")

foreach(required
    "${POLATORY_LIBRARY}"
    "${SCALFMM_INCLUDE}"
    "${POLATORY_TRIPLET}/include"
    "${LIBOMP_LIBRARY}")
  if(NOT EXISTS "${required}")
    message(FATAL_ERROR "Required frozen build input does not exist: ${required}")
  endif()
endforeach()

add_library(rapidrbf_scalfmm_probe SHARED
  rapidrbf_scalfmm_probe.cpp
  rapidrbf_scalfmm_probe.h
)

target_compile_features(rapidrbf_scalfmm_probe PRIVATE cxx_std_20)
target_compile_definitions(rapidrbf_scalfmm_probe PRIVATE
  EIGEN_DONT_PARALLELIZE
  EIGEN_MPL2_ONLY
  EIGEN_USE_BLAS
  NOMINMAX
  RRSF_BUILDING_DLL
  WIN32_LEAN_AND_MEAN
)
target_compile_options(rapidrbf_scalfmm_probe PRIVATE
  /bigobj
  /W4
  /wd4702
  -Wno-unused-command-line-argument
  -Xclang
  -fopenmp
)
target_include_directories(rapidrbf_scalfmm_probe PRIVATE
  "${POLATORY_ROOT}/include"
  "${SCALFMM_INCLUDE}"
  "${POLATORY_TRIPLET}/include"
  "${POLATORY_TRIPLET}/include/eigen3"
  "${POLATORY_TRIPLET}/include/fftw"
)
target_link_libraries(rapidrbf_scalfmm_probe PRIVATE
  "${POLATORY_LIBRARY}"
  "${LIBOMP_LIBRARY}"
  "${POLATORY_TRIPLET}/lib/intel64/mkl_intel_lp64_dll.lib"
  "${POLATORY_TRIPLET}/lib/intel64/mkl_sequential_dll.lib"
  "${POLATORY_TRIPLET}/lib/intel64/mkl_core_dll.lib"
  shlwapi
)
set_target_properties(rapidrbf_scalfmm_probe PROPERTIES
  CXX_EXTENSIONS OFF
  MSVC_RUNTIME_LIBRARY MultiThreadedDLL
  OUTPUT_NAME "rapidrbf_scalfmm_probe"
)

add_executable(rapidrbf_scalfmm_c_smoke abi_header_smoke.c)
target_compile_features(rapidrbf_scalfmm_c_smoke PRIVATE c_std_11)
target_link_libraries(rapidrbf_scalfmm_c_smoke PRIVATE rapidrbf_scalfmm_probe)
