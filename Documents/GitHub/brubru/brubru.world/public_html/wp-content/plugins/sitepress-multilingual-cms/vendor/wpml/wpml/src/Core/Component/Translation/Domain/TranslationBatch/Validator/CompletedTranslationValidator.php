<?php

namespace WPML\Core\Component\Translation\Domain\TranslationBatch\Validator;

use WPML\Core\Component\Translation\Domain\CompletedTranslationDetector;
use WPML\Core\Component\Translation\Domain\HowToHandleExistingTranslationType;
use WPML\Core\Component\Translation\Domain\TranslationBatch\Element;
use WPML\Core\Component\Translation\Domain\TranslationBatch\TargetLanguage;
use WPML\Core\Component\Translation\Domain\TranslationBatch\TranslationBatch;
use WPML\Core\Component\Translation\Domain\TranslationMethod\AutomaticMethod;


class CompletedTranslationValidator implements ValidatorInterface {

  const IGNORED_ELEMENT_REASON = 'content_already_translated';

  /** @var CompletedTranslationDetector */
  private $completedTranslationDetector;


  public function __construct( CompletedTranslationDetector $completedTranslationDetector ) {
    $this->completedTranslationDetector = $completedTranslationDetector;
  }


  /**
   * We shall ignore already translated element if
   *  - the chosen translation method is automatic
   *  - a user chose not to override existing translations
   *
   * @param TranslationBatch $translationBatch
   *
   * @return array{0: TranslationBatch, 1: IgnoredElement[]}
   */
  public function validate( TranslationBatch $translationBatch ): array {
    if (
      $translationBatch->getHowToHandleExisting() ===
      HowToHandleExistingTranslationType::HANDLE_EXISTING_OVERRIDE
    ) {
      return [ $translationBatch, [] ];
    }

    $ignoredElements = [];
    $targetLanguages = [];
    foreach ( $translationBatch->getTargetLanguages() as $targetLanguage ) {
      if ( $targetLanguage->getMethod() instanceof AutomaticMethod ) {
        $correctElements = [];

        foreach ( $targetLanguage->getElements() as $element ) {
          if ( $this->hasCompletedTranslationInGivenLanguage( $element, $targetLanguage->getLanguageCode() ) ) {
            $ignoredElements[] = new IgnoredElement(
              $element->getType(),
              $element->getElementId(),
              $targetLanguage->getLanguageCode(),
              $targetLanguage->getMethod(),
              self::IGNORED_ELEMENT_REASON
            );
          } else {
            $correctElements[] = $element;
          }
        }

        $targetLanguages[] = new TargetLanguage(
          $targetLanguage->getLanguageCode(),
          $targetLanguage->getMethod(),
          $correctElements
        );
      } else {
        $targetLanguages[] = $targetLanguage;
      }
    }

    $translationBatch = $translationBatch->copyWithNewTargetLanguages( $targetLanguages );

    return [ $translationBatch, $ignoredElements ];
  }


  private function hasCompletedTranslationInGivenLanguage( Element $element, string $languageCode ): bool {
    $existingTranslations = $element->getExistingTranslations();

    foreach ( $existingTranslations as $translation ) {
      if ( $translation->getTargetLanguageCode() === $languageCode ) {

        if ( $this->completedTranslationDetector->isTranslationCompleted(
          $translation->getStatus()->get(),
          $translation->needsUpdate(),
          $translation->getId(),
          $translation->getTranslatedElementId()
        ) ) {
          return true;
        }
      }
    }

    return false;
  }


}
