"""Evenemangskällor. Varje källa hämtar rådata (fetch) och gör om den till appens format (normalize)."""

from sources.ccc import CCC
from sources.scala import Scala
from sources.shl import SHL
from sources.ticketmaster import Ticketmaster
from sources.visitvarmland import VisitVarmland

# Ordningen avgör prioritet vid sammanslagning av dubbletter: den första är rikast.
SOURCES = [VisitVarmland(), Ticketmaster(), CCC(), Scala(), SHL()]
