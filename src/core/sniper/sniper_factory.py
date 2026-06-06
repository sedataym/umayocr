from src.core.sniper.base_sniper import BaseSniper
from src.core.sniper.slurp_sniper import SlurpSniper
from src.core.sniper.core_sniper import CoreSniper

class SniperFactory:
    @staticmethod
    def get_engine() -> BaseSniper:
        # Currently only Slurp (Wayland) is supported.
        # Future implementations can check OS/DE and return the appropriate engine.
        #return SlurpSniper()
        return CoreSniper()
