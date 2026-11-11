#ifndef MOON_TEST_CLOCK_FRAMEWORK_H
#define MOON_TEST_CLOCK_FRAMEWORK_H
typedef struct {unsigned int size,abi;int (*read_seconds)(double *);} ProbeClockFrameworkV1;
#endif
