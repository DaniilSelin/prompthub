import sqlite3
from core.domain.model_tariff import ModelTariff


class TariffManager:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def bulk_upsert(self, tariffs: list[ModelTariff]) -> int:
        """Открывает транзакцию, делает INSERT или UPDATE для каждого тарифа.
        При ошибке откатывает транзакцию. Возвращает количество обработанных записей."""
        try:
            cur = self.conn.cursor()
            cur.execute("BEGIN")
            for tariff in tariffs:
                existing = self._find_by_model(cur, tariff.tag_name)
                if existing:
                    cur.execute(
                        """UPDATE model_tariffs
                           SET input_price_per_1k = ?,
                               output_price_per_1k = ?,
                               updated_at = CURRENT_TIMESTAMP
                           WHERE tag_name = ?""",
                        (tariff.input_price_per_1k, tariff.output_price_per_1k, tariff.tag_name),
                    )
                else:
                    cur.execute(
                        """INSERT INTO model_tariffs (tag_name, input_price_per_1k, output_price_per_1k)
                           VALUES (?, ?, ?)""",
                        (tariff.tag_name, tariff.input_price_per_1k, tariff.output_price_per_1k),
                    )
            self.conn.commit()
            return len(tariffs)
        except sqlite3.Error as e:
            try:
                self.conn.rollback()
            except sqlite3.Error:
                pass
            raise RuntimeError(f"Ошибка записи в базу данных: {e}") from e

    def _find_by_model(self, cur: sqlite3.Cursor, tag_name: str):
        cur.execute(
            "SELECT tag_name FROM model_tariffs WHERE tag_name = ?", (tag_name,)
        )
        return cur.fetchone()
