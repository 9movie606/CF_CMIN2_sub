import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("generate", ROOT / "scripts" / "generate.py")
generate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generate)


class ParseTests(unittest.TestCase):
    def test_default_port(self):
        key, endpoint = generate.parse_endpoint("1.2.3.4", 1)
        self.assertEqual(key, ("1.2.3.4", 443))
        self.assertEqual(endpoint, "1.2.3.4:443")

    def test_custom_port(self):
        key, endpoint = generate.parse_endpoint("1.2.3.4:8443", 1)
        self.assertEqual(key, ("1.2.3.4", 8443))
        self.assertEqual(endpoint, "1.2.3.4:8443")

    def test_explicit_empty_port_is_rejected(self):
        with self.assertRaisesRegex(generate.DataError, "端口不能为空"):
            generate.parse_endpoint("1.2.3.4:", 1)

    def test_same_ip_different_ports_are_distinct(self):
        self.assertNotEqual(
            generate.parse_endpoint("1.2.3.4:443", 1)[0],
            generate.parse_endpoint("1.2.3.4:8443", 2)[0],
        )

    def test_two_cities_promote_to_province(self):
        regions = generate.parse_regions("广东/深圳,广东/广州", 1)
        self.assertEqual(regions, [("广东", None)])

    def test_mixed_province_and_other_province_city_is_allowed(self):
        regions = generate.parse_regions("广东,江苏/南京", 1)
        self.assertEqual(set(regions), {("广东", None), ("江苏", "南京")})

    def test_same_province_and_city_is_rejected(self):
        with self.assertRaises(generate.DataError):
            generate.parse_regions("广东,广东/深圳", 1)

    def test_uncertain_region_is_rejected(self):
        with self.assertRaises(generate.DataError):
            generate.parse_regions("云南/昆明?", 1)

    def test_duplicate_endpoint_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "input.txt"
            source.write_text("1.2.3.4|广东\n1.2.3.4:443|浙江\n", encoding="utf-8")
            with self.assertRaisesRegex(generate.DataError, "重复节点"):
                generate.load_records(source)


class BuildTests(unittest.TestCase):
    def test_province_city_all_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            source = tmp / "input.txt"
            output = tmp / "dist"
            source.write_text(
                "1.1.1.1|广东\n"
                "2.2.2.2|广东/深圳\n"
                "3.3.3.3:8443|江苏/南京,湖北\n",
                encoding="utf-8",
            )
            index = generate.build(source, output)

            guangdong = (output / "province" / "guangdong.txt").read_text(encoding="utf-8")
            self.assertEqual(guangdong.splitlines(), ["1.1.1.1:443#广东"])

            shenzhen = (output / "city" / "guangdong" / "深圳.txt").read_text(encoding="utf-8")
            self.assertEqual(set(shenzhen.splitlines()), {
                "1.1.1.1:443#广东-深圳", "2.2.2.2:443#广东-深圳"
            })

            hubei = (output / "province" / "hubei.txt").read_text(encoding="utf-8")
            self.assertEqual(hubei.splitlines(), ["3.3.3.3:8443#湖北"])
            jiangsu = output / "province" / "jiangsu.txt"
            self.assertFalse(jiangsu.exists(), "沒有省級節點時不應生成空省級 TXT")

            all_lines = (output / "all.txt").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(all_lines), 3)
            self.assertTrue(any("3.3.3.3:8443#湖北_江苏/南京" == line for line in all_lines))
            self.assertEqual(index["total"], 3)
            self.assertEqual(index["province_total"], 2)
            self.assertEqual(index["city_total"], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
