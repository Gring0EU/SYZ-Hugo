"""Put showcase.json and the Syz logo into template.html: showcase/syz_data_lab.html."""
import base64, json, os
HERE = os.path.dirname(os.path.abspath(__file__))
t = open(os.path.join(HERE, "template.html"), encoding="utf-8").read()
data = json.load(open(os.path.join(HERE, "data", "showcase.json")))
logo = base64.b64encode(open(os.path.join(HERE, "..", "termsheet-studio", "syz_logo.png"), "rb").read()).decode()
page = t.replace("__LOGO__", logo).replace("__DATA__", json.dumps(data, separators=(",", ":")).replace("</", "<\\/"))
open(os.path.join(HERE, "syz_data_lab.html"), "w", encoding="utf-8").write(page)
print("showcase/syz_data_lab.html written")
