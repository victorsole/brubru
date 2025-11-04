<?php

namespace WPML\Core\Component\WordsToTranslate\Domain;

interface ProviderInterface {


  /**
   * @param int $id
   * @param string $type
   * @param string[] $langs
   * @param bool $freshTranslation When true, previous translations will be
   * ignored.
   *
   * @return Item|false
   */
  public function getByIdAndTypeForLangs( $id, $type, $langs, $freshTranslation = false );


  /**
   * @param int $id
   * @param string $type
   * @param TranslatableDTO[] $content
   *
   * @return void
   */
  public function useThisContentForItem( $id, $type, $content );


}
