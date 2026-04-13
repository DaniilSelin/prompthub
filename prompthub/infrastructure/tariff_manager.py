import sqlite3

from prompthub.core.domain.model_tariff import ModelTariff


class TariffManager:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def bulk_upsert(self, tariffs: list[ModelTariff]) -> int:
        """INSERT OR REPLACE для каждого тарифа в одной транзакции.
        При ошибке откатывает транзакцию. Возвращает количество обработанных записей."""
        try:
            cur = self.conn.cursor()
            cur.execute("BEGIN")
            for tariff in tariffs:
                cur.execute(
                    """
                    INSERT INTO model_tariffs
                        (tag_name, input_price_per_1m, output_price_per_1m, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(tag_name) DO UPDATE SET
                        input_price_per_1m  = excluded.input_price_per_1m,
                        output_price_per_1m = excluded.output_price_per_1m,
                        updated_at         = CURRENT_TIMESTAMP
                    """,
                    (
                        tariff.tag_name,
                        tariff.input_price_per_1m,
                        tariff.output_price_per_1m,
                    ),
                )
            self.conn.commit()
            return len(tariffs)
        except sqlite3.Error as e:
            try:
                self.conn.rollback()
            except sqlite3.Error:
                pass
            raise RuntimeError(f"Ошибка записи в базу данных: {e}") from e
