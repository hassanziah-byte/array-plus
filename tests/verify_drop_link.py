"""Check the README drag & drop link with Blender's own drop-handling functions.
Needs a profile where the repository (releases/latest/download/index.json) was added and synced:
  blender --online-mode --command extension repo-add --url <index url> array_plus_repo
  blender --online-mode --command extension sync
Run: blender -b --python tests/verify_drop_link.py -- "<drag link>"
"""
import bpy, sys, json
from bl_pkg.bl_extension_utils import url_parse_for_blender
from bl_pkg.bl_extension_ops import extension_url_find_repo_index_and_pkg_id

link = sys.argv[sys.argv.index("--") + 1]
url, params = url_parse_for_blender(link)
repos = bpy.context.preferences.extensions.repos
known = [r.remote_url for r in repos if r.use_remote_url]
found = extension_url_find_repo_index_and_pkg_id(url)
print("JSON>>" + json.dumps({
    "stripped_url": url,
    "params": params,
    "repository_matches_added_repo": params.get("repository") in known,
    "lookup": [x if isinstance(x, (int, str)) else type(x).__name__ for x in found] if found else None,
    "repo_name": repos[found[0]].name if found and found[0] >= 0 else None,
}))
