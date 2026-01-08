<?php

namespace WPML\Core\Component\WordsToTranslate\Domain\Post\Query;

use WPML\Core\Component\WordsToTranslate\Domain\Post\Post;
use WPML\Core\Component\WordsToTranslate\Domain\Post\Term\Term;
use WPML\Core\Component\WordsToTranslate\Domain\Post\Term\TermContent;


interface TranslationQueryInterface {


  /**
   * Returns the last translated original content (original = source language).
   *
   * @param Post $post
   * @param string $lang
   * @param string[] $fieldsToTranslate
   *
   * @return string
   */
  public function getLastTranslatedOriginalContentForPost(
    $post,
    $lang,
    $fieldsToTranslate
  );


  /** @return bool */
  public function isTermTranslatable( Term $term, string $lang );


  /** @return string */
  public function getLastTranslatedOriginalContentForTermContent(
    Term $term,
    TermContent $termContent,
    string $langCode
  );


}
