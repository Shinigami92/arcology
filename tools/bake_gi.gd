extends SceneTree
## Bakes every VoxelGI in a zone scene and saves the data next to the scene.
##
## Usage (not headless; the voxelizer needs a renderer):
##   "$GODOT4_EDITOR" --path . --xr-mode off --script res://tools/bake_gi.gd -- --scene=res://zones/apartment/apartment.tscn
## Writes <scene_dir>/<scene_name>_<gi_name>.voxelgi.res and re-saves the
## scene with the data assigned. Re-run after changing static geometry or
## emissive materials. Close the scene in the editor first (or reload it after).


func _initialize() -> void:
	var scene_path := ""
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--scene="):
			scene_path = arg.substr(8)
	if scene_path.is_empty():
		push_error("bake_gi: pass -- --scene=res://path/to/zone.tscn")
		quit(2)
		return

	var packed := load(scene_path) as PackedScene
	var root := packed.instantiate()
	get_root().add_child(root)
	# Let the scene settle (tool scripts, meshes) before voxelizing.
	await process_frame
	await process_frame

	var text := FileAccess.get_file_as_string(scene_path)
	var baked := 0
	for node in root.find_children("*", "VoxelGI", true, false):
		var gi := node as VoxelGI
		var started := Time.get_ticks_msec()
		gi.bake(root)
		if not gi.data:
			push_error("bake_gi: %s produced no data" % root.get_path_to(gi))
			continue
		var data_path := "%s/%s_%s.voxelgi.res" % [
				scene_path.get_base_dir(), scene_path.get_file().get_basename(), gi.name.to_snake_case()]
		ResourceSaver.save(gi.data, data_path)
		text = _assign_data(text, root.get_path_to(gi), data_path)
		print("bake_gi: %s -> %s (%d ms)" % [root.get_path_to(gi), data_path, Time.get_ticks_msec() - started])
		baked += 1

	if baked > 0:
		# Patch the .tscn text instead of re-packing the instance, so the file
		# keeps only authored values (no runtime state, no copied base values).
		var out := FileAccess.open(scene_path, FileAccess.WRITE)
		out.store_string(text)
		out.close()
		print("bake_gi: patched ", scene_path)
	quit(0 if baked > 0 else 1)


## Adds (or reuses) an ext_resource for [param data_path] and sets it as the
## data of the VoxelGI node at [param node_path] in the scene text.
static func _assign_data(text: String, node_path: NodePath, data_path: String) -> String:
	var ext_id := "voxelgi_" + str(node_path).to_snake_case().replace("/", "_")
	var ext_line := '[ext_resource type="VoxelGIData" path="%s" id="%s"]' % [data_path, ext_id]
	if not text.contains('id="%s"' % ext_id):
		var first_sub := text.find("

[sub_resource")
		var first_node := text.find("

[node")
		var insert_at := first_sub if first_sub != -1 else first_node
		text = text.insert(insert_at, "
" + ext_line)

	var name := str(node_path).get_file()
	var parent := str(node_path).get_base_dir()
	var header := '[node name="%s" type="VoxelGI" parent="%s"' % [name, parent if parent != "" else "."]
	var at := text.find(header)
	if at == -1:
		push_error("bake_gi: node header not found: " + header)
		return text
	var body_start := text.find("
", at) + 1
	var body_end := text.find("
[", body_start)
	var body := text.substr(body_start, body_end - body_start)
	var lines := body.split("
")
	var kept: PackedStringArray = []
	for line in lines:
		if not line.begins_with("data = "):
			kept.append(line)
	var assign := 'data = ExtResource("%s")' % ext_id
	# Keep the blank line that separates this node from the next one.
	if kept.size() > 0 and kept[kept.size() - 1] == "":
		kept.insert(kept.size() - 1, assign)
	else:
		kept.append(assign)
	return text.substr(0, body_start) + "
".join(kept) + text.substr(body_end)
