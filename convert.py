import os
import argparse
import json
import base64
from selenium import webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver import ChromeOptions

if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("--input", "-i", type=str, default=None,
                        help="The json input. Exported from Safari.")
    parser.add_argument("--output", "-o", type=str, default=None,
                        help="Name of the gif output.")
    parser.add_argument("--delay", "-d", type=int, default=10,
                        help="The delay parameter for ImageMagick.")

    args = parser.parse_args()

    assert args.input, "No input file provided!"

    prefix = args.input.split(".")[0]
    if not args.output:
        args.output = prefix + ".gif"

    with open(args.input, "r") as f:
        j = json.load(f)

    data = j["data"]

    # read in the provided images
    all_images = ""
    for i, d in enumerate(data):
        if type(d) == str and d[:22] == "data:image/png;base64,":
            all_images += f"<img id=\"{i}\" src=\"{d}\" style=\"display:none\"/>\n"

    # get indices of getImageData results in the json
    all_saved_idx = []
    for frame in j["frames"]:
        for action in frame["actions"]:
            # FIXME: the logic here is probably incorrect
            if action[0] == 67:
                all_saved_idx.append(action[1][0])

    # generate all commands
    all_commands = ""
    saved_idx = 0

    for frame in j["frames"]:
        actions = frame["actions"]

        for action in actions:
            # for safari-specific export format, refer to the json file
            num = action[0]

            # 49 is drawImage
            if num == 49:
                idx = action[1][0]
                x = action[1][1]
                y = action[1][2]

                all_commands += f"Image = document.getElementById(\"{idx}\");"
                all_commands += f"context.drawImage(Image, {x}, {y});"

            # 33 is clearRect
            if num == 33:
                x = action[1][0]
                y = action[1][1]
                w = action[1][2]
                h = action[1][3]

                all_commands += f"context.clearRect({x}, {y}, {w}, {h});"

            # 61 is getImageData
            if num == 61:
                x = action[1][0]
                y = action[1][1]
                w = action[1][2]
                h = action[1][3]

                all_commands += f"ImageData{saved_idx} = context.getImageData({x}, {y}, {w}, {h});"

                saved_idx += 1

            # 67 is putImageData
            if num == 67:

                idx = action[1][0]
                x = action[1][1]
                y = action[1][2]

                if idx not in all_saved_idx:
                    all_saved_idx.append(idx)

                all_commands += f"context.putImageData(ImageData{all_saved_idx.index(idx)}, {x}, {y});"

        # the generated frames are printed to the logs
        all_commands += "console.log(canvas.toDataURL(\"png\"));"

    # currently the canvas size is fixed
    saved_html = "<html><head><script type=\"text/javascript\">var canvas, context, Image;function init() {canvas = document.getElementById(\"can\");context = canvas.getContext(\"2d\");" + \
        all_commands + "}</script></head><body onload=\"init()\"><canvas id=\"can\" height=\"220\" width=\"220\"></canvas>" + \
        all_images + "</body></html>"

    with open("temp.html", "w") as f:
        f.write(saved_html)

    # enable log
    dc = DesiredCapabilities.CHROME
    dc["goog:loggingPrefs"] = {"browser": "ALL"}

    # headless
    chrome_options = ChromeOptions()
    chrome_options.add_argument("--headless")
    driver = webdriver.Chrome(options=chrome_options, desired_capabilities=dc)

    # launch browser
    driver.get("file://" + os.getcwd() + "/temp.html")

    # get log
    log = driver.get_log("browser")

    # create image directory
    if not os.path.exists(f"images-{prefix}"):
        os.mkdir(f"images-{prefix}")

    # save images
    for i, l in enumerate(log):
        try:
            image_string = l["message"].split("\"")[1][22:]
        except:
            print(l["message"])
            exit()
        png_recovered = base64.decodebytes(
            bytes(image_string, encoding="utf-8"))
        f = open(f"images-{prefix}/{i:03}.png", "wb")
        f.write(png_recovered)
        f.close()

    # call convert to generate gif
    os.system(
        f"convert -background white -alpha remove -layers OptimizePlus -delay {args.delay} -loop 0 images-{prefix}/*.png {args.output}")

    # quit driver
    driver.quit()
