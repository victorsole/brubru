<?php

namespace WPML\Core\Component\WordsToTranslate\Domain\Post\Query;

use WPML\Core\Component\WordsToTranslate\Domain\Post\JobDto;
use WPML\Core\Component\WordsToTranslate\Domain\Post\Post;
use WPML\Core\Component\WordsToTranslate\Domain\Post\Term\Term;
use WPML\Core\Component\WordsToTranslate\Domain\TranslatableDTO;

interface JobQueryInterface {


  /** @return Term[] */
  public function getTerms( Post $post );


  /** @return JobDto */
  public function getContentToTranslateForLang( Post $post, string $lang );


  /**
   * @param int $idItem
   * @param TranslatableDTO[] $content
   *
   * @return void
   */
  public function useThisContentForItem( $idItem, $content );


}
