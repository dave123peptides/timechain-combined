"use client";

import { useState } from "react";
import ProductImagePlaceholder from "./ProductImagePlaceholder";
import styles from "./ProductGallery.module.css";

export default function ProductGallery({ images, name }: { images: string[]; name: string }) {
  const [activeIndex, setActiveIndex] = useState(0);

  if (images.length === 0) {
    return (
      <div className={styles.mainWrap}>
        <ProductImagePlaceholder name={name} />
      </div>
    );
  }

  const activeImage = images[Math.min(activeIndex, images.length - 1)];

  return (
    <div>
      <div className={styles.mainWrap}>
        {/* eslint-disable-next-line @next/next/no-img-element -- product images are arbitrary external URLs from Product.images */}
        <img src={activeImage} alt={name} className={styles.mainImage} />
      </div>
      {images.length > 1 && (
        <div className={styles.thumbs}>
          {images.map((image, index) => (
            <button
              key={image}
              type="button"
              className={`${styles.thumb} ${index === activeIndex ? styles.thumbActive : ""}`}
              onClick={() => setActiveIndex(index)}
              aria-label={`Show image ${index + 1} of ${images.length}`}
            >
              {/* eslint-disable-next-line @next/next/no-img-element -- product images are arbitrary external URLs from Product.images */}
              <img src={image} alt="" className={styles.thumbImage} />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
