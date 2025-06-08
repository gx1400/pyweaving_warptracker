from wif import WIFReader
from pathlib import Path
from render import ImageRenderer
from PIL import Image, ImageDraw

def load_draft(infile):
    if infile.endswith('.wif'):
        return WIFReader(infile).read()
    else:
        raise ValueError(
            "filename %r unrecognized: .wif and .json are supported" %
            infile)

def main():
    filename = r'D:\repos\pyweaving\pyweaving\Overshot_Honeysuckle-LP.wif'
    filepath = Path(filename)
    
    if not filepath.exists():
        print(f"File {filename} does not exist.")
        return
    print("This is the main function.")
    draft = load_draft(filename)
    renderer = ImageRenderer(draft)
    renderer.show()
    lp = print_LiftPlan(draft)
    print(lp)
    
    #renderer.save('test.png')
    
    #lp = draft.liftplan;
    width = 34 + renderer.pixels_per_square * len(draft.shafts)
    height = 6 + renderer.pixels_per_square * len(draft.weft)
    im = Image.new("RGB", (width,height), (255, 255, 255))
    draw = ImageDraw.Draw(im)

    renderer.paint_liftplan(draw)
    im.show()
    
def print_LiftPlan(draft):
    num_threads = len(draft.weft)
    liftplan = []
    for ii, thread in enumerate(draft.weft):
        shafts = []
        for jj, shaft in enumerate(draft.shafts):
                if shaft in thread.connected_shafts:
                    shafts.append(jj+1)
        liftplan.append(shafts)
    return liftplan

if __name__ == "__main__":
    main()