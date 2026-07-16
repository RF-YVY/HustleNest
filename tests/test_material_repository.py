from __future__ import annotations

import gc
import os
import tempfile
import unittest
from unittest.mock import patch

from hustlenest.data import database, material_repository
from hustlenest.models.order_models import Material


class MaterialRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._cleanup_temporary_directory)
        self._environment = patch.dict(
            os.environ,
            {"LOCALAPPDATA": self._temporary_directory.name},
        )
        self._environment.start()
        self.addCleanup(self._environment.stop)
        database.initialize()

    def _cleanup_temporary_directory(self) -> None:
        gc.collect()
        self._temporary_directory.cleanup()

    def test_save_material_inserts_every_material_field(self) -> None:
        material_id = material_repository.save_material(
            Material(
                id=None,
                sku="MAT-001",
                name="Cotton Fabric",
                category="Fabric",
                description="Natural cotton",
                unit_of_measure="yard",
                quantity_on_hand=12.5,
                reorder_point=3.0,
                cost_per_unit=4.25,
                vendor_id=None,
                notes="Keep dry",
                lead_time_days=5,
                archived=False,
            )
        )

        saved = material_repository.get_material(material_id)

        self.assertIsNotNone(saved)
        assert saved is not None
        self.assertEqual(saved.sku, "MAT-001")
        self.assertEqual(saved.name, "Cotton Fabric")
        self.assertEqual(saved.category, "Fabric")
        self.assertEqual(saved.description, "Natural cotton")
        self.assertEqual(saved.unit_of_measure, "yard")
        self.assertEqual(saved.quantity_on_hand, 12.5)
        self.assertEqual(saved.reorder_point, 3.0)
        self.assertEqual(saved.cost_per_unit, 4.25)
        self.assertEqual(saved.notes, "Keep dry")
        self.assertEqual(saved.lead_time_days, 5)
        self.assertFalse(saved.archived)


if __name__ == "__main__":
    unittest.main()
