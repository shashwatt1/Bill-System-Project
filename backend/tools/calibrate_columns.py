import sys
import cv2

clicked_x_values = []

def mouse_callback(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        img_copy = param["temp_img"]
        print(f"X: {x}, Y: {y}")
        cv2.line(img_copy, (x, 0), (x, img_copy.shape[0]), (255, 0, 0), 2)
        cv2.imshow("Calibration", img_copy)
        clicked_x_values.append(x)

def main():
    if len(sys.argv) < 2:
        print("Usage: python calibrate_columns.py <path_to_image>")
        sys.exit(1)
        
    img_path = sys.argv[1]
    img = cv2.imread(img_path)
    
    if img is None:
        print(f"Could not load image at {img_path}")
        sys.exit(1)
        
    print(f"Image dimensions: {img.shape[1]}x{img.shape[0]} (width x height)")
    
    temp_img = img.copy()
    cv2.namedWindow("Calibration")
    cv2.setMouseCallback("Calibration", mouse_callback, param={"temp_img": temp_img})
    cv2.imshow("Calibration", temp_img)
    
    print("Click to place a vertical line and log X,Y. Press 'q' to quit.")
    
    while True:
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
            
    cv2.destroyAllWindows()
    
    print("\n--- Calibration Summary ---")
    print(f"Clicked X values: {sorted(clicked_x_values)}")

if __name__ == "__main__":
    main()
