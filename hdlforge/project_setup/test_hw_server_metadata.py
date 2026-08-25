from datetime import datetime, timezone
import unittest

import hw_server_tasks


def _epoch(year: int, month: int, day: int, hour: int) -> int:
    return int(datetime(year, month, day, hour, tzinfo=timezone.utc).timestamp())


class FirmwareMetadataFormattingTest(unittest.TestCase):
    def test_timestamp_formats_use_cdt(self) -> None:
        userid = _epoch(2026, 8, 25, 16)

        self.assertEqual(
            hw_server_tasks._format_timestamp(userid),
            "2026-08-25 11:00:00 CDT (0x6A8DBC00)",
        )
        self.assertEqual(
            hw_server_tasks._format_timestamp(userid, output_type="artifact"),
            "2026_08_25-11h_00m_00s_CDT",
        )
        self.assertEqual(
            hw_server_tasks._format_timestamp(userid, output_type="config"),
            "2026-08-25 11:00",
        )

    def test_timestamp_formats_use_cst(self) -> None:
        userid = _epoch(2026, 1, 15, 18)

        self.assertEqual(
            hw_server_tasks._format_timestamp(userid),
            "2026-01-15 12:00:00 CST (0x69692B20)",
        )
        self.assertEqual(
            hw_server_tasks._format_timestamp(userid, output_type="release"),
            "20260115_120000",
        )

    def test_version_formats_share_one_function(self) -> None:
        usr_access = 0x00030000

        self.assertEqual(hw_server_tasks._format_version(usr_access), "v3.0.0")
        self.assertEqual(
            hw_server_tasks._format_version(usr_access, output_type="display"),
            "v3.0.0 (0x00030000)",
        )
        self.assertEqual(
            hw_server_tasks._format_version(usr_access, output_type="artifact"),
            "v3.0",
        )


if __name__ == "__main__":
    unittest.main()
