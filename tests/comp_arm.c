/* ARM entry for tests/test_comp.py: the production compressor at a fixed address. */
#include "../src/joebox_comp.h"
__attribute__((used,section(".entry"))) void jc_entry(struct jc_state *s,unsigned mode,float thresh,float *l,float *r,int n) {
    jc_process(s,mode,thresh,l,r,n);
}
