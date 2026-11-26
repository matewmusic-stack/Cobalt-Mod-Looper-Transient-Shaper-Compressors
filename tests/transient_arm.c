/* ARM entry for tests/test_transient.py: the production shaper at a fixed address. */
#include "../src/transient_shaper.h"
__attribute__((used,section(".entry"))) void ts_entry(struct ts_state *s,const struct ts_params *p,float *l,float *r,int n) {
    ts_process(s,p,l,r,n);
}
