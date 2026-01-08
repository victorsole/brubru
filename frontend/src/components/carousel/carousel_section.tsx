// frontend/src/components/carousel/carousel_section.tsx
import { useState } from 'react';
import './carousel_section.css';

const CAROUSEL_MESSAGES: Record<string, string> = {
  'beresol_bear_pandora.png': 'For those who opened the Pandora crypto-box.',
  'brubru_mainlogo.png': 'Meet Brubru, Your AI-powered EU policy assistant. Navigate the EU Bubble with confidence.',
  'beresol_lito_electricity.png': 'For those who work on energy.',
  'beresol_lito_housing_crisis.png': 'For those worried about the rampant housing crisis.',
  'brubru_amendator.png': 'Draft Perfect Amendments. Our AI helps you craft legislative amendments that follow official formatting and best practices.',
  'beresol_lito_robottoys.png': 'For those playing with the new AI toys.',
  'beresol_lito_ursi.png': 'For those who want to monitor EU policies and laws easily.',
  'brubru_profile.png': 'Your Personal EU Profile. Track your interests, saved searches, and stay updated on what matters to you.',
  'beresol_lito_ursi_robots.png': 'For those who want to know how Europe legislates AI.',
  'beresol_pixar.png': 'Beresol the Bear will always be there for you.',
  'brubru_myeububble.png': 'Manage All Your EU Bubble Projects.',
  'cat_boxes.png': 'For those like Lito, trying to understand the EU\'s +50k laws.',
  'lito_beresol_drones.png': 'For those who will have to comply with the new EU defence policy.',
};

const CAROUSEL_IMAGES = [
  'beresol_bear_pandora.png',
  'brubru_mainlogo.png',
  'beresol_lito_electricity.png',
  'beresol_lito_housing_crisis.png',
  'brubru_amendator.png',
  'beresol_lito_robottoys.png',
  'beresol_lito_ursi.png',
  'brubru_profile.png',
  'beresol_lito_ursi_robots.png',
  'beresol_pixar.png',
  'brubru_myeububble.png',
  'cat_boxes.png',
  'lito_beresol_drones.png',
];

export const CarouselSection = () => {
  const [flippedCards, setFlippedCards] = useState<Set<number>>(new Set());

  // Duplicate the images 3 times for seamless loop
  const duplicatedImages = [...CAROUSEL_IMAGES, ...CAROUSEL_IMAGES, ...CAROUSEL_IMAGES];

  const handleCardClick = (index: number) => {
    const newFlipped = new Set(flippedCards);
    if (newFlipped.has(index)) {
      newFlipped.delete(index);
    } else {
      newFlipped.add(index);
      // Auto flip back after 6 seconds
      setTimeout(() => {
        setFlippedCards(prev => {
          const updated = new Set(prev);
          updated.delete(index);
          return updated;
        });
      }, 6000);
    }
    setFlippedCards(newFlipped);
  };

  return (
    <section className="carousel">
      <div className="carousel__container">
        <div className="carousel__track">
          {duplicatedImages.map((image, index) => (
            <div
              key={`${image}-${index}`}
              className={`carousel__card ${flippedCards.has(index) ? 'carousel__card--flipped' : ''}`}
              onClick={() => handleCardClick(index)}
            >
              <div className="carousel__card-inner">
                {/* Front - Image */}
                <div className="carousel__card-front">
                  <img
                    src={`/assets/carousel/${image}`}
                    alt={image.replace('.png', '')}
                    className="carousel__image"
                  />
                </div>
                {/* Back - Text */}
                <div className="carousel__card-back">
                  <p className="carousel__message">{CAROUSEL_MESSAGES[image]}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};
