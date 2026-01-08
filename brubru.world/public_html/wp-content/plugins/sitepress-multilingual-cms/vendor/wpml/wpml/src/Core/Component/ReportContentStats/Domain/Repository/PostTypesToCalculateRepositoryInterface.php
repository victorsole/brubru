<?php

namespace WPML\Core\Component\ReportContentStats\Domain\Repository;

interface PostTypesToCalculateRepositoryInterface {


  /** @return string[]|null */
  public function get();


  /**
   * @param string[] $postTypes
   *
   * @return void
   */
  public function init( array $postTypes );


  /** @return void */
  public function removePostType( string $postTypeName );


  /** @return void */
  public function delete();


}
