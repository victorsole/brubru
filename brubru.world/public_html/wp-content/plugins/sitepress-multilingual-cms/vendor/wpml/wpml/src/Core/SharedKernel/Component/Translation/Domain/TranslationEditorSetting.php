<?php

namespace WPML\Core\SharedKernel\Component\Translation\Domain;

class TranslationEditorSetting {

  const ATE = 'ATE';
  const CLASSIC = 'CTE';
  const MANUAL = 'MANUAL';
  const PRO = 'PRO';

  /** @var string */
  private $value;

  /**
   * It determines if the ATE should be used for old translations created with CTE or we should stick to CTE.
   *
   * @var bool
   */
  private $useAteForOldTranslationsCreatedWithCte = false;

  /** @var bool */
  private $useNativeEditorGlobally;

  /** @var array<mixed> */
  private $useNativeEditorPerPostType;


  /**
   * @param string                    $value
   * @param mixed                     $useNativeEditorGlobally
   * @param array<string, bool>|mixed $useNativeEditorPerPostType
   */
  public function __construct(
    string $value,
    $useNativeEditorGlobally = false,
    $useNativeEditorPerPostType = []
  ) {
    $this->value = in_array( $value, $this->getAll() ) ? $value : self::CLASSIC;
    $this->useNativeEditorGlobally = $useNativeEditorGlobally === true;
    $this->useNativeEditorPerPostType = (array) $useNativeEditorPerPostType;
  }


  /**
   * @return string[]
   */
  public function getAll(): array {
    return [
      self::ATE,
      self::CLASSIC,
      self::MANUAL,
      self::PRO,
    ];
  }


  public function getValue(): string {
    return $this->value;
  }


  public function useAteForOldTranslationsCreatedWithCte(): bool {
    return $this->useAteForOldTranslationsCreatedWithCte;
  }


  public function setUseAteForOldTranslationsCreatedWithCte( bool $useAteForOldTranslationsCreatedWithCte ): self {
    $this->useAteForOldTranslationsCreatedWithCte = $useAteForOldTranslationsCreatedWithCte;

    return $this;
  }


  public static function createDefault(): self {
    return new self( self::ATE );
  }


  public function useNativeEditorForAllPostTypes() : bool {
    return $this->useNativeEditorGlobally;
  }


  /**
   * @return array<string, bool>
   */
  public function getPostTypesUsingNativeEditor() : array {
    $validatedData = [];
    foreach ( $this->useNativeEditorPerPostType as $postType => $useNativeEditor ) {
      $validatedData[ (string) $postType ] = (bool) $useNativeEditor;
    }

    return $validatedData;
  }


}
