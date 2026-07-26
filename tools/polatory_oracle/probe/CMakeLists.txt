cmake_minimum_required(VERSION 3.20)

project(polatory_frozen_source_probe LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
if(NOT CMAKE_CONFIGURATION_TYPES AND NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
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

set(POLATORY_FROZEN_COMMIT "4a30beb08053fb339ce899e255be4b6d3f74aa0c")

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
        "The diagnostic probe requires Polatory ${POLATORY_FROZEN_COMMIT}, "
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
    message(
        FATAL_ERROR
        "POLATORY_SOURCE_DIR must have no tracked modifications so the recorded revision "
        "identifies its headers"
    )
endif()

set(Eigen3_DIR "${POLATORY_EIGEN3_DIR}")
find_package(Eigen3 CONFIG REQUIRED)

add_executable(polatory_frozen_source_probe probe.cpp)
target_include_directories(
    polatory_frozen_source_probe
    PRIVATE
    "${POLATORY_SOURCE_DIR}/include"
)
target_link_libraries(polatory_frozen_source_probe PRIVATE Eigen3::Eigen)
target_compile_definitions(
    polatory_frozen_source_probe
    PRIVATE
    EIGEN_DONT_PARALLELIZE
    EIGEN_MPL2_ONLY
    POLATORY_FROZEN_COMMIT="${POLATORY_FROZEN_COMMIT}"
)

if(MSVC)
    target_compile_options(polatory_frozen_source_probe PRIVATE /EHsc /fp:precise)
else()
    target_compile_options(polatory_frozen_source_probe PRIVATE -fno-fast-math)
endif()
