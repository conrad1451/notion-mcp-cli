"""Flattens and sorts tags from a nested JSON hierarchy into a flat sorted list."""

# CHQ: ChatGPT generated this tool to flatten and sort the tags from a json
#      file so that file could be compared with another to catch
#      missing tags that must be added to the json file. This helps keep
#      the tags file up to date when new tags are added to the database
# works with the output of scaffold_tags.py to ensure that the program
# always has the latest version of tags from databases

import json


def flatten_and_sort_tags(tag_data):
    """Recursively flatten a nested tag structure and return sorted list of tags."""
    results = []

    def walk(node):
        if isinstance(node, list):
            for item in node:
                if isinstance(item, str):
                    results.append(item)
                else:
                    walk(item)
        elif isinstance(node, dict):
            for value in node.values():
                walk(value)

    walk(tag_data)

    return sorted(results, key=lambda s: s.lower())


input_list = [
    "../database_metadata/tag_categories_apr10at12amupdate.json",
    "../database_metadata/rescal_versions/data_structure/tag_categories_v8.json",
    "../database_metadata/rescal_versions/data_structure/tag_categories_v8_5.json",
    "../database_metadata/rescal_versions/data_structure/tag_categories_v9_2.json",
    "../database_metadata/rescal_versions/data_structure/tag_categories_v9_3.json",
    "../database_metadata/rescal_versions/data_structure/tag_categories_v9_4.json",
    "../database_metadata/rescal_versions/data_structure/tag_categories_v9_4_5.json",
    "../database_metadata/rescal_versions/data_structure/tag_categories_v9_5v1.json",
    "../database_metadata/rescal_versions/data_structure/9_5v2.json",
    "../database_metadata/rescal_versions/data_structure/tag_categories_v9_6.json",
    "../database_metadata/rescal_versions/data_structure/tag_categories_v9_8.json",
    "../database_metadata/tag_categorieswk16.json",
    "../database_metadata/tag_categories.json",
    "../database_metadata/tag_categories_unsorted.json",
    "../database_metadata/tag_categories.json",
]

output_list = [
    "flat_tags_sorted_apr10at1232am.json",
    "../database_metadata/rescal_versions/flat_list/flat_tag_categories_v8.json",
    "../database_metadata/rescal_versions/flat_list/flat_tag_categories_v8_5.json",
    "../database_metadata/rescal_versions/flat_list/flat_tag_categories_v9_2.json",
    "../database_metadata/rescal_versions/flat_list/flat_tag_categories_v9_3.json",
    "../database_metadata/rescal_versions/flat_list/flat_tag_categories_v9_4.json",
    "../database_metadata/rescal_versions/flat_list/flat_tag_categories_v9_4_5.json",
    "../database_metadata/rescal_versions/flat_list/flat_tag_categories_v9_5v1.json",
    "../database_metadata/rescal_versions/flat_list/flat_tag_9_5v2.json",
    "../database_metadata/rescal_versions/flat_list/flat_tag_categories_v9_6.json",
    "../database_metadata/rescal_versions/flat_list/flat_tag_categories_v9_8.json",
    "../database_metadata/rescal_versions/flat_list/flat_tag_categories_wk16.json",
    "../database_metadata/rescal_versions/flat_list/flat_tag_categories_current_wk17.json",
    "../database_metadata/rescal_versions/flat_list/flat_tag_categories_unsorted.json",
    "../database_metadata/rescal_versions/flat_list/flat_tag_categories_sorted.json",
]

# input_file = "../database_metadata/tag_categories.json"
input_file = input_list[-1]  # pylint: disable=invalid-name
output_file = output_list[-1]  # pylint: disable=invalid-name

with open(input_file, "r", encoding="utf-8") as f:
    data = json.load(f)

flat_sorted = flatten_and_sort_tags(data)

with open(output_file, "w", encoding="utf-8") as f:
    json.dump(flat_sorted, f, indent=2, ensure_ascii=False)

print(f"Saved flattened sorted tags to {output_file}")
