from dataclasses import dataclass


@dataclass
class ModelTariff:
    tag_name: str
    input_price_per_1m: float
    output_price_per_1m: float
