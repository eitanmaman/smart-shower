#include <cassert>
#include "../firmware/SmartShower/Session.h"
int main() {
  const uint8_t a[] = {1,2,3,4}, b[] = {5,6,7,8};
  Session s;
  assert(!s.open);
  s.begin(a,4,1000); assert(s.open && s.same(a,4) && !s.same(b,4));
  assert(s.seconds(61000)==60);
  s.begin(b,4,61000); assert(s.seconds(62000)==1 && s.same(b,4));
  s.begin(a,4,0xFFFFFF00UL); assert(s.seconds(0x000006D0UL)==2);
  ScanGate g;
  assert(g.update(true,0));
  assert(!g.update(true,5000)); // Held card never retriggers based only on time.
  assert(!g.update(false,5100)); assert(!g.update(false,5800));
  assert(!g.update(true,5801)); // Removal <750 ms is not enough.
  g.update(false,6000); g.update(false,6750);
  assert(g.update(true,6800));
}
