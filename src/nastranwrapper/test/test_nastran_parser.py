import os
import pkg_resources
import unittest
from openmdao.main.api import SimulationRoot
from nastranwrapper.nastran_parser import NastranParser, \
     readable_header

ORIG_DIR = os.getcwd()
DIRECTORY = pkg_resources.resource_filename('nastranwrapper', 'test')

class TestNastranParser(unittest.TestCase):

    def setUp(self):
        SimulationRoot.chroot(DIRECTORY)

    def tearDown(self):
        SimulationRoot.chroot(ORIG_DIR)

    def go(self, filename):
        fh = open(filename, "r")
        text = fh.readlines()
        fh.close()
        self.parser = NastranParser(text)
        self.parser.parse()
        self.assertTrue(len(self.parser.headers) == len(self.parser.grids))
        self.assertTrue(len(self.parser.headers) == len(self.parser.subcases))

        # make sure the table is really a grid
        self.assertTrue(len(set([len(row) for row in self.parser.grids[0]])) == 1)

    def test_simple(self):
        self.go("practice-grid.1.txt")

        # check the header's right
        clean = self.parser.headers[0]["clean"]
        self.assertTrue(clean == "displacement vector")

        grid = self.parser.grids[0]
        # check that the columns are right
        self.assertTrue(grid[0] == \
            ["POINT ID.", "TYPE", "T1", "T2", "T3", "R1", "R2", "R3"])

        # if the columns are right, it probably didn't mangle up the values
        # but we can do some quick checks just in case.
        self.assertTrue(grid[1][1].strip() == "G")
        self.assertAlmostEqual(float(grid[2][2]), -6.514980e-19)
        self.assertAlmostEqual(float(grid[4][6]), 2.281463e-01)

        # we can also check the get function because its important
        [[r2]] = self.parser.get("displacement vector", 1,
                             {"POINT ID." : "17"}, ["R2"])

        self.assertAlmostEqual(float(r2), 2.451840E-01)

    def test_repeated_columns(self):
        self.go("practice-grid.2.txt")
        clean = self.parser.headers[0]["clean"]
        self.assertTrue(clean == "stresses in rod elements (crod)")
        grid = self.parser.grids[0]

        # look at that, it collapsed the two columns
        self.assertTrue(grid[0] == \
                        ["ELEMENT ID.", "AXIAL STRESS", "SAFETY MARGIN", \
                         "TORSIONAL STRESS", "SAFETY MARGIN"])

        # and all three rows are there (+header)
        # note, there is actually an extra row of blank spaces
        # that isn't hurting anyone.
        self.assertTrue(len(grid) >= 4)

        # sanity
        self.assertAlmostEqual(float(grid[3][2]), -8.0e-01)
        self.assertAlmostEqual(float(grid[2][1]), 2.779327e+05)

        # the getter must be checked
        ax = self.parser.get("stresses in rod elements (crod)",\
                             1, {}, ["AXIAL STRESS"])
        ax = [x[0] for x in ax]
        self.assertAlmostEqual(float(ax[0]), 3.273509E+05)
        self.assertAlmostEqual(float(ax[1]), 2.779327E+05)
        self.assertAlmostEqual(float(ax[2]), 1.005818E+05)

    def test_family_confusion(self):
        self.go("practice-grid.3.txt")
        h = "stresses in layered composite elements (quad4)"
        self.assertTrue(h == self.parser.headers[0]["clean"])

        grid = self.parser.grids[0]

        self.assertTrue(grid[0] == ["ELEMENT ID", "PLY ID",
            "STRESSES IN FIBER AND MATRIX DIRECTIONS NORMAL-1",
            "STRESSES IN FIBER AND MATRIX DIRECTIONS NORMAL-2",
            "STRESSES IN FIBER AND MATRIX DIRECTIONS SHEAR-12",
            "INTER-LAMINAR  STRESSES SHEAR XZ-MAT",
            "INTER-LAMINAR  STRESSES SHEAR YZ-MAT",
            "PRINCIPAL STRESSES (ZERO SHEAR) ANGLE",
            "PRINCIPAL STRESSES (ZERO SHEAR) MAJOR",
            "PRINCIPAL STRESSES (ZERO SHEAR) MINOR",
            "MAX SHEAR"])

        # sanity
        [[stress]] = self.parser.get(h, 1, {"ELEMENT ID":"1", "PLY ID":"3"}, \
                                     ["PRINCIPAL STRESSES (ZERO SHEAR) MAJOR"])
        self.assertAlmostEqual(float(stress), 1.66126E+05)


    # this test is just amazingly annoying.
    # It has headings (element id, plane 1, plane 2, but
    # also families of headings (plane 1 and 2 belong to BEND-MOMENT END-A)
    # unfortunately, nastran makes it almost impossible to tell whether
    # or not something's a family or a header without being a human
    # So, heuristics.
    def test_family_confusion_and_dash_in_header(self):
        self.go("practice-grid.7.txt")
        h = "forces in bar elements (cbar)"
        self.assertTrue(h == self.parser.headers[0]["clean"])

        grid = self.parser.grids[0]
        self.assertTrue(grid[0] == ["ELEMENT ID.", \
                                    "BEND-MOMENT END-A PLANE 1", \
                                    "BEND-MOMENT END-A PLANE 2", \
                                    "BEND-MOMENT END-B PLANE 1", \
                                    "BEND-MOMENT END-B PLANE 2", \
                                    "- SHEAR - PLANE 1", \
                                    "- SHEAR - PLANE 2", \
                                    "AXIAL FORCE",
                                    "TORQUE",])

    # this example is a little funny. It has zeroes at the beginning
    # and no subcase, mostly due to the fact that the subcase is in the grid
    def test_funny(self):
        self.go("practice-grid.4.txt")
        h = "maximum applied loads"
        self.assertTrue(h == self.parser.headers[0]["clean"])

        grid = self.parser.grids[0]
        self.assertTrue(grid[0] == \
                        ["SUBCASE/ DAREA ID", "T1", "T2", "T3",\
                         "R1", "R2", "R3"])
        # the first row also parses correctly. hoora
        self.assertTrue(grid[1] == ["1", "5.0000000E+04", "1.0000000E+05", \
                                    "0.0000000E+00", "0.0000000E+00", \
                                    "0.0000000E+00", "0.0000000E+00"])

        # what happens when we query the getter?
        [[t2]] = self.parser.get("maximum applied loads", \
                                 None, {"SUBCASE/ DAREA ID" : "1"},
                                 ["T2"])

        self.assertAlmostEqual(float(t2), 1e5)

    def test_spaces_in_headers_and_annoying_header(self):
        self.go("practice-grid.5.txt")
        h = "real eigenvector no.2"

        self.assertTrue(h in self.parser.headers[0]["clean"])

        [[t1]] = self.parser.get(h, 1, {"POINT ID.": "1"}, ["T1"])
        self.assertAlmostEqual(float(t1), 8.089535E-01)

        [[t2]] = self.parser.get(h, 1, {"POINT ID.": "2"}, ["T2"])
        self.assertAlmostEqual(float(t2), 1.0)


    def test_spaces_in_multiple_headers(self):
        self.go("practice-grid.6.txt")
        h = "forces of single-point constraint"

        self.assertTrue(self.parser.headers[0]["clean"] == h)
        grid = self.parser.grids[0]
        self.assertTrue(grid[0] == ["POINT ID.", "TYPE", "T1", \
                                    "T2", "T3", "R1", "R2", "R3"])
        [[t1]] = self.parser.get(h, 1, {"POINT ID." : "2"}, ["T1"])
        self.assertAlmostEqual(float(t1), -1.252551E+05)

        [[r2]] = self.parser.get(h, 1, {"POINT ID." : "2"}, ["R2"])
        self.assertAlmostEqual(float(r2), 0)

    def test_row_width(self):
        self.go("practice-grid.row-width.txt")
        h = "S T R E S S E S   I N   Q U A D R I L A T E R A L   E L E M E N T S   ( Q U A D 4 )        OPTION = BILIN"

        self.assertTrue(self.parser.headers[0]["actual"].strip() == h)
        grid = self.parser.grids[0]
        self.assertTrue(grid[0] == ["ELEMENT ID", "GRID-ID", "FIBER DISTANCE", "STRESSES IN ELEMENT COORD SYSTEM NORMAL-X", \
                                    "STRESSES IN ELEMENT COORD SYSTEM NORMAL-Y", "STRESSES IN ELEMENT COORD SYSTEM SHEAR-XY", \
                                    "PRINCIPAL STRESSES (ZERO SHEAR) ANGLE", "PRINCIPAL STRESSES (ZERO SHEAR) MAJOR", \
                                    "PRINCIPAL STRESSES (ZERO SHEAR) MINOR", "VON MISES"])

        vonmises = self.parser.get(h, None, {}, ["VON MISES"])
        self.assertTrue(vonmises[:2] == [['9.012409E+03'], ['1.252266E+04']])
        for x in vonmises:
            self.assertTrue(len(x) == 1)

        big_group = self.parser.get(h, None, {}, ["VON MISES"], row_width=15)
        self.assertTrue(len(big_group[0]) == 15)

        # row_width with some constraints
        element_2 = self.parser.get(h, None, {"ELEMENT ID" : "2"}, ["VON MISES"], row_width=15)
        self.assertTrue(len(element_2[0]) == 15)
        self.assertTrue(element_2[0][:2] == [['8.079449E+03'], ['1.242515E+04']])



if __name__ == "__main__":
    unittest.main()
