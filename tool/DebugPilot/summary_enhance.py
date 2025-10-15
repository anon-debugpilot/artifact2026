import sys
import os
import json

def rebuild_decision(plan):
	new_plan = []
	for method_step in plan:
		new_method_step = {
			"method": method_step["method"],
			"src_path": method_step["src_path"],
			"plan": []
        }
		for idx, ite_step in enumerate(method_step["plan"]):
			if idx == 0:
				new_ite_step = {
					"focus": "Method Body",
					"analysis": "BlockList Partition",
					"decision": "BlockList 0",
					"start_line": ite_step["start_line"],
					"end_line": ite_step["end_line"],
					"options": [
						{
							"id": 0,
							"start_line": ite_step["start_line"],
                            "end_line": ite_step["end_line"],
							"comment": "BlockList 0 (default)",
							"status": 1,
							"trace": -1
                        }
					]
                }
				new_method_step["plan"].append(new_ite_step)
				new_ite_step = {
                    "focus": "Method Body",
					"analysis": "Block Selection",
					"decision": "",
					"start_line": ite_step["start_line"],
                    "end_line": ite_step["end_line"],
					"options": ite_step["options"]
                }
				for id, option in enumerate(new_ite_step["options"]):
					if option["status"] == 1:
						new_ite_step["decision"] = f"Block {id}"
						new_method_step["plan"][-1]["options"][0]["trace"] = option["trace"]
						break
				new_method_step["plan"].append(new_ite_step)
			elif ite_step["phase"] == "locating":
				new_ite_step = {
					"focus": ite_step["focus"],
					"analysis": "Oracle Inference",
					"decision": "Inconsistent",
					"start_line": ite_step["start_line"],
                    "end_line": ite_step["end_line"],
					"options": [
						{
							"id": 0,
							"start_line": ite_step["start_line"],
                            "end_line": ite_step["end_line"],
							"comment": "Consistent",
							"status": 0,
							"trace": ite_step["options"][0]["trace"]
                        },
						{
							"id": 1,
							"start_line": ite_step["start_line"],
                            "end_line": ite_step["end_line"],
							"comment": "Inconsistent",
							"status": 1,
							"trace": ite_step["options"][0]["trace"]
                        }
                    ]
                }
				new_method_step["plan"].append(new_ite_step)
				new_ite_step = {
					"focus": ite_step["focus"],
					"analysis": "Partition Check",
					"decision": "Impartible",
					"start_line": ite_step["start_line"],
                    "end_line": ite_step["end_line"],
					"options": [
						{
							"id": 0,
							"start_line": ite_step["start_line"],
                            "end_line": ite_step["end_line"],
							"comment": "Partiable. Narrow Down",
							"status": 0,
							"trace": ite_step["options"][0]["trace"]
                        },
						{
							"id": 1,
							"start_line": ite_step["start_line"],
                            "end_line": ite_step["end_line"],
							"comment": "Impartible",
							"status": 1,
							"trace": ite_step["options"][0]["trace"]
                        }
                    ]
                }
				new_method_step["plan"].append(new_ite_step)
				new_ite_step = {
					"focus": ite_step["focus"],
					"analysis": "Fault Localization",
					"decision": "",
					"start_line": ite_step["start_line"],
                    "end_line": ite_step["end_line"],
					"options": ite_step["options"]
                }
				for id, option in enumerate(new_ite_step["options"]):
					if option["status"] == 1:
						if id == 0:
							new_ite_step["decision"] = "Root Cause"
						else:
							new_ite_step["decision"] = f"Step in Method {option['comment']}"
						break
				new_method_step["plan"].append(new_ite_step)
			else:
				new_ite_step = {
					"focus": ite_step["focus"],
					"analysis": "Oracle Inference",
					"decision": "Inconsistent",
					"start_line": ite_step["start_line"],
                    "end_line": ite_step["end_line"],
					"options": [
						{
							"id": 0,
							"start_line": ite_step["start_line"],
                            "end_line": ite_step["end_line"],
							"comment": "Consistent",
							"status": 0,
							"trace": -1
                        },
						{
							"id": 1,
							"start_line": ite_step["start_line"],
                            "end_line": ite_step["end_line"],
							"comment": "Inconsistent",
							"status": 1,
							"trace": -1
                        }
                    ]
                }
				new_method_step["plan"].append(new_ite_step)
				new_ite_step = {
					"focus": ite_step["focus"],
					"analysis": "Partition Check",
					"decision": "Narrow Down",
					"start_line": ite_step["start_line"],
                    "end_line": ite_step["end_line"],
					"options": [
						{
							"id": 0,
							"start_line": ite_step["start_line"],
                            "end_line": ite_step["end_line"],
							"comment": "Partiable. Narrow Down",
							"status": 1,
							"trace": -1
                        },
						{
							"id": 1,
							"start_line": ite_step["start_line"],
                            "end_line": ite_step["end_line"],
							"comment": "Impartible",
							"status": 0,
							"trace": -1
                        }
                    ]
                }
				prefix = "Sub" + "sub" * (idx - 1)
				new_method_step["plan"].append(new_ite_step)
				new_ite_step = {
					"focus": ite_step["focus"],
					"analysis": "BlockList Partition",
					"decision": f"{prefix}BlockList 0",
					"start_line": ite_step["start_line"],
					"end_line": ite_step["end_line"],
					"options": [
						{
							"id": 0,
							"start_line": ite_step["start_line"],
                            "end_line": ite_step["end_line"],
							"comment": f"{prefix}BlockList 0 (default)",
							"status": "selected",
							"trace": -1
                        }
					]
                }
				new_method_step["plan"].append(new_ite_step)
				new_ite_step = {
                    "focus": ite_step["focus"],
					"analysis": "Block Selection",
					"decision": "",
					"start_line": ite_step["start_line"],
                    "end_line": ite_step["end_line"],
					"options": ite_step["options"]
                }
				for id, option in enumerate(new_ite_step["options"]):
					if option["status"] == 1:
						new_ite_step["decision"] = f"{prefix}Block {id}"
						new_method_step["plan"][-1]["options"][0]["trace"] = option["trace"]
						new_method_step["plan"][-2]["options"][0]["trace"] = option["trace"]
						new_method_step["plan"][-2]["options"][1]["trace"] = option["trace"]
						new_method_step["plan"][-3]["options"][0]["trace"] = option["trace"]
						new_method_step["plan"][-3]["options"][1]["trace"] = option["trace"]
						break
				new_method_step["plan"].append(new_ite_step)
		new_plan.append(new_method_step)
	return new_plan

def move_spec(plan):
	new_plan = []
	for method_step in plan:
		new_method_step = {
			"method": method_step["method"],
			"src_path": method_step["src_path"],
			"plan": []
        }
		for ite_step in method_step["plan"]:
			if ite_step["analysis"] == "Block Selection":
				new_ite_step = {
					"focus": ite_step["focus"],
					"analysis": ite_step["analysis"],
					"decision": ite_step["decision"],
					"start_line": ite_step["start_line"],
					"end_line": ite_step["end_line"],
					"options": []
				}
				for option in ite_step["options"]:
					if option["status"] == 1:
						temp = option
						new_option = {
							"id": option["id"],
							"start_line": option["start_line"],
							"end_line": option["end_line"],
							"comment": option["comment"],
							"status": option["status"],
							"trace": option["trace"]
						}
						new_ite_step["options"].append(new_option)
					else:
						new_ite_step["options"].append(option)
				new_method_step["plan"].append(new_ite_step)
			elif ite_step["analysis"] == "Oracle Inference":
				new_ite_step = {
					"focus": ite_step["focus"],
					"analysis": ite_step["analysis"],
					"decision": ite_step["decision"],
					"start_line": ite_step["start_line"],
					"end_line": ite_step["end_line"],
					"options": []
				}
				for option in ite_step["options"]:
					if option["status"] == 1:
						new_option = {
							"id": option["id"],
							"start_line": option["start_line"],
							"end_line": option["end_line"],
							"comment": option["comment"],
							"status": option["status"],
							"trace": option["trace"],
							"specification": temp["specification"],
							"oracle": temp["oracle"],
							"match": temp["match"],
							"summary": temp["summary"],
							"consistent": temp["consistent"]
						}
						new_ite_step["options"].append(new_option)
					else:
						new_ite_step["options"].append(option)
				new_method_step["plan"].append(new_ite_step)
			else:
				new_method_step["plan"].append(ite_step)
		new_plan.append(new_method_step)
	return new_plan

def main():
	if len(sys.argv) != 3:
		print("usage: python summary_enhance.py <project_name> <bug_id>")
		print("e.g.: python summary_enhance.py Chart 24")
		sys.exit(1)

	project_name = sys.argv[1]
	bug_id = sys.argv[2]
	project_dir = f"{project_name}_{bug_id}"
	result_dir = os.path.join("result", project_dir)
	plan_path = os.path.join(result_dir, "debugging_plan.json")
	enhanced_path = os.path.join(result_dir, "debugging_plan.json")

	if not os.path.exists(plan_path):
		print(f"Error: {plan_path} not found")
		sys.exit(1)
	with open(plan_path, "r", encoding="utf-8") as f:
		plan = json.load(f)

	enhanced_plan = rebuild_decision(plan)
	enhanced_plan = move_spec(enhanced_plan)

	with open(enhanced_path, "w", encoding="utf-8") as f:
		json.dump(enhanced_plan, f, indent=4, ensure_ascii=False)
	print(f"enhanced summary: {enhanced_path}")

if __name__ == "__main__":
	main()