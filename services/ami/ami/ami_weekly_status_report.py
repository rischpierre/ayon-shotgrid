import sys;sys.path.append("/cache/dev/sandbox/rvx/scratches")
from path_templates import StringTemplate
import corder


def test_corder():
    template = "ami/test_corder.xlsx"
    out_file = "ami/test_corder_out.xlsx"

    crd = corder.Corder(template)
    crd.parse_replacements()

    data = {"project": {"name": "Flow_pet_project"}, "root": "dev", "version": {"id": 21342}}

    # set values on tags
    for tag in crd.tags:
        stemplate = StringTemplate(tag)
        value = stemplate.format(data)
        crd.replacements[tag].set_value(str(value))

    crd.fill()
    crd.write(out_file)


def test_corder_range():
    # todo this works
    template = "ami/test_corder_range.xlsx"
    out_file = "ami/test_corder_range_out.xlsx"

    objects = [
        {"project": {"name": "Flow_pet_project"}, "root": "dev", "version": {"id": 21342}},
        {"project": {"name": "Flow_pet_project"}, "root": "toto", "version": {"id": 2324}},
    ]

    crd = corder.Corder(template)
    crd.parse_replacements()

    rows = []
    rng = crd.range("version")  # or your range type as defined in the template
    for obj in objects:
        row = {}
        for tag in rng.tags:
            # Render the tag against your object
            rendered = StringTemplate(tag).format(obj)
            # If your StringTemplate returns an object with .missing_keys/.invalid_types, handle as needed
            value = "" if getattr(rendered, "missing_keys", []) or getattr(rendered, "invalid_types", []) else str(
                rendered)
            row[tag] = value
        rows.append(row)

    rng.set_replacement_values(rows)
    crd.fill()
    crd.write(out_file)

def test_template():
    tpl = StringTemplate("/{root}/{project[name]}/asdgasdg")
    data = {"project": {"name": "Flow_pet_project"}, "root": "dev", "version": {"id": 21342}}
    print(tpl.format(data))

if __name__ == "__main__":
    # test_template()
    # test_corder()
    test_corder_range()