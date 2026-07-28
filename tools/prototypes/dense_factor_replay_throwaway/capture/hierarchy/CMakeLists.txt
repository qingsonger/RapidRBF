cmake_minimum_required(VERSION 3.20)

project(rapidrbf_hierarchy_capture_throwaway LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
if(CMAKE_CONFIGURATION_TYPES)
    set(CMAKE_CONFIGURATION_TYPES Release CACHE STRING "Frozen capture configuration" FORCE)
elseif(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
elseif(NOT CMAKE_BUILD_TYPE STREQUAL "Release")
    message(FATAL_ERROR "The frozen capture requires CMAKE_BUILD_TYPE=Release")
endif()

set(
    POLATORY_SOURCE_DIR
    "D:/CODE/polatory"
    CACHE PATH
    "Path to the clean Polatory source tree at the frozen revision"
)
set(
    POLATORY_EIGEN3_DIR
    "${POLATORY_SOURCE_DIR}/build/vcpkg_installed/x64-windows/share/eigen3"
    CACHE PATH
    "Path to the Eigen3 CMake package used by the frozen Polatory build"
)
set(
    POLATORY_MKL_LIB_DIR
    "${POLATORY_SOURCE_DIR}/build/vcpkg_installed/x64-windows/lib/intel64"
    CACHE PATH
    "Path to the layered oneMKL import libraries used by frozen Polatory"
)
set(
    POLATORY_MKL_BIN_DIR
    "${POLATORY_SOURCE_DIR}/build/vcpkg_installed/x64-windows/bin"
    CACHE PATH
    "Path to the layered oneMKL runtime used by frozen Polatory"
)
set(POLATORY_FROZEN_COMMIT "4a30beb08053fb339ce899e255be4b6d3f74aa0c")

if(
    NOT MSVC
    OR NOT CMAKE_CXX_COMPILER_ID STREQUAL "Clang"
    OR NOT CMAKE_CXX_SIMULATE_ID STREQUAL "MSVC"
    OR NOT CMAKE_CXX_COMPILER_VERSION VERSION_EQUAL "19.1.5"
)
    message(
        FATAL_ERROR
        "The frozen capture requires clang-cl 19.1.5 with the MSVC frontend"
    )
endif()

find_package(Git REQUIRED)
execute_process(
    COMMAND "${GIT_EXECUTABLE}" -C "${POLATORY_SOURCE_DIR}" rev-parse HEAD
    RESULT_VARIABLE POLATORY_GIT_RESULT
    OUTPUT_VARIABLE POLATORY_ACTUAL_COMMIT
    ERROR_VARIABLE POLATORY_GIT_ERROR
    OUTPUT_STRIP_TRAILING_WHITESPACE
)
if(NOT POLATORY_GIT_RESULT EQUAL 0)
    message(FATAL_ERROR "Cannot identify POLATORY_SOURCE_DIR: ${POLATORY_GIT_ERROR}")
endif()
if(NOT POLATORY_ACTUAL_COMMIT STREQUAL POLATORY_FROZEN_COMMIT)
    message(
        FATAL_ERROR
        "Capture requires Polatory ${POLATORY_FROZEN_COMMIT}, "
        "but POLATORY_SOURCE_DIR is at ${POLATORY_ACTUAL_COMMIT}"
    )
endif()
execute_process(
    COMMAND "${GIT_EXECUTABLE}" -C "${POLATORY_SOURCE_DIR}" status --porcelain --untracked-files=no
    RESULT_VARIABLE POLATORY_STATUS_RESULT
    OUTPUT_VARIABLE POLATORY_STATUS
    ERROR_VARIABLE POLATORY_STATUS_ERROR
    OUTPUT_STRIP_TRAILING_WHITESPACE
)
if(NOT POLATORY_STATUS_RESULT EQUAL 0)
    message(FATAL_ERROR "Cannot inspect POLATORY_SOURCE_DIR: ${POLATORY_STATUS_ERROR}")
endif()
if(NOT POLATORY_STATUS STREQUAL "")
    message(FATAL_ERROR "POLATORY_SOURCE_DIR must have no tracked modifications")
endif()

set(Eigen3_DIR "${POLATORY_EIGEN3_DIR}")
find_package(Eigen3 CONFIG REQUIRED)
if(NOT Eigen3_VERSION VERSION_EQUAL "5.0.1")
    message(
        FATAL_ERROR
        "The frozen vcpkg Eigen package coordinate is 5.0.1, found ${Eigen3_VERSION}"
    )
endif()

add_executable(rapidrbf_hierarchy_capture ../hierarchy_capture.cpp)
target_include_directories(
    rapidrbf_hierarchy_capture
    PRIVATE
    "${POLATORY_SOURCE_DIR}/include"
)
target_link_libraries(rapidrbf_hierarchy_capture PRIVATE Eigen3::Eigen)

set(
    MKL_IMPORT_CLOSURE
    "mkl_intel_lp64_dll.lib|487b430c0a2bcca41dc40abcab8cbc18471701b621efb850136f6d45821f5db4"
    "mkl_sequential_dll.lib|3859198460bd0d04a617a7fecb9ceb9c18f7e8b14ebcb439a0eebaca7b9d01b2"
    "mkl_core_dll.lib|110c0433d4665f8535174059d9042992cd88e566c7b2b13281fd776a7d46cc02"
)
foreach(MKL_IMPORT_SPEC IN LISTS MKL_IMPORT_CLOSURE)
    string(REPLACE "|" ";" MKL_IMPORT_FIELDS "${MKL_IMPORT_SPEC}")
    list(GET MKL_IMPORT_FIELDS 0 MKL_IMPORT_LIBRARY)
    list(GET MKL_IMPORT_FIELDS 1 MKL_IMPORT_SHA256)
    set(MKL_IMPORT_PATH "${POLATORY_MKL_LIB_DIR}/${MKL_IMPORT_LIBRARY}")
    if(NOT EXISTS "${MKL_IMPORT_PATH}")
        message(FATAL_ERROR "Missing frozen oneMKL import library: ${MKL_IMPORT_LIBRARY}")
    endif()
    file(SHA256 "${MKL_IMPORT_PATH}" MKL_IMPORT_ACTUAL_SHA256)
    if(NOT MKL_IMPORT_ACTUAL_SHA256 STREQUAL MKL_IMPORT_SHA256)
        message(
            FATAL_ERROR
            "oneMKL import hash mismatch for ${MKL_IMPORT_LIBRARY}: "
            "${MKL_IMPORT_ACTUAL_SHA256}"
        )
    endif()
    target_link_libraries(
        rapidrbf_hierarchy_capture
        PRIVATE
        "${MKL_IMPORT_PATH}"
    )
endforeach()

target_compile_definitions(
    rapidrbf_hierarchy_capture
    PRIVATE
    EIGEN_DONT_PARALLELIZE
    EIGEN_MPL2_ONLY
    EIGEN_USE_BLAS
    POLATORY_FROZEN_COMMIT="${POLATORY_FROZEN_COMMIT}"
    RAPIDRBF_CAPTURE_BUILD_MODE="$<CONFIG>"
    RAPIDRBF_CAPTURE_FLOAT_MODE="clang-cl-fp-precise-fast-math-disabled"
)
target_compile_options(
    rapidrbf_hierarchy_capture
    PRIVATE
    /EHsc
    /W4
    /WX
    /wd4702
    /bigobj
    /fp:precise
    /Brepro
    -Wno-unused-command-line-argument
)
target_link_options(
    rapidrbf_hierarchy_capture
    PRIVATE
    /Brepro
    /INCREMENTAL:NO
)

set(
    MKL_RUNTIME_CLOSURE
    "mkl_core.2.dll|3e7edb4328abf430b62c7c75e33447042dc8033f0cc75910708fd3bb5f27c792"
    "mkl_sequential.2.dll|478fda28a98021fb7f95b27b2876cac7346d77c4a491003ba0f50baf17b66fe3"
    "mkl_def.2.dll|0aff76a9a8c4618c1f467bf08334ec3a93e92ada04b62f31864c8f052bea9745"
    "mkl_avx2.2.dll|cc85f0c3b1f0f02998a14923037873530645a77039e95a6a3fb90a7d01468d41"
)
foreach(MKL_RUNTIME_SPEC IN LISTS MKL_RUNTIME_CLOSURE)
    string(REPLACE "|" ";" MKL_RUNTIME_FIELDS "${MKL_RUNTIME_SPEC}")
    list(GET MKL_RUNTIME_FIELDS 0 MKL_RUNTIME_LIBRARY)
    list(GET MKL_RUNTIME_FIELDS 1 MKL_RUNTIME_SHA256)
    set(MKL_RUNTIME_PATH "${POLATORY_MKL_BIN_DIR}/${MKL_RUNTIME_LIBRARY}")
    if(NOT EXISTS "${MKL_RUNTIME_PATH}")
        message(FATAL_ERROR "Missing frozen oneMKL runtime: ${MKL_RUNTIME_LIBRARY}")
    endif()
    file(SHA256 "${MKL_RUNTIME_PATH}" MKL_RUNTIME_ACTUAL_SHA256)
    if(NOT MKL_RUNTIME_ACTUAL_SHA256 STREQUAL MKL_RUNTIME_SHA256)
        message(
            FATAL_ERROR
            "oneMKL runtime hash mismatch for ${MKL_RUNTIME_LIBRARY}: "
            "${MKL_RUNTIME_ACTUAL_SHA256}"
        )
    endif()
    add_custom_command(
        TARGET rapidrbf_hierarchy_capture
        POST_BUILD
        COMMAND
            "${CMAKE_COMMAND}" -E copy_if_different
            "${MKL_RUNTIME_PATH}"
            "$<TARGET_FILE_DIR:rapidrbf_hierarchy_capture>/${MKL_RUNTIME_LIBRARY}"
        VERBATIM
    )
endforeach()
