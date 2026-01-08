<?php

namespace WPML\Core\Component\WordsToTranslate\Domain\Job\Query;

use WPML\Core\Component\WordsToTranslate\Domain\TranslatableDTO;

interface JobQueryInterface {


  /**
   * @param int $id
   *
   * @return string
   */
  public function getSourceLang( $id );


  /**
   * @param int $id
   *
   * @return string
   */
  public function getTargetLang( $id );


  /**
   * @param int $id
   *
   * @return bool
   */
  public function isAutomatic( $id );


  /**
   * @param int $id
   *
   * @return int[]
   */
  public function getPreviousAteJobIds( $id );


  /**
   * @param int $id
   *
   * @return int
   */
  public function getJobItemId( $id );


  /**
   * @param int $id
   *
   * @return string
   */
  public function getJobItemType( $id );


  /**
   * @param int $id
   *
   * @return TranslatableDTO[]
   */
  public function getContent( $id );


  /**
   * @param int $id
   *
   * @return ?int
   */
  public function getWordsToTranslate( $id );


  /**
   * @param int $id
   *
   * @return ?int
   */
  public function getAutomaticTranslationCosts( $id );


}
