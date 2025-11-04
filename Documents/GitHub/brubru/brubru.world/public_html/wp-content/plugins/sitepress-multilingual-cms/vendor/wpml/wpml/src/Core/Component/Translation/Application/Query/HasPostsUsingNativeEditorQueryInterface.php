<?php

namespace WPML\Core\Component\Translation\Application\Query;

use WPML\Core\Port\Persistence\Exception\DatabaseErrorException;

interface HasPostsUsingNativeEditorQueryInterface {


  /**
   * @param string[] $postTypes
   * @param string[] $postTypesUsingWpEditor
   *
   * @throws DatabaseErrorException
   * @return bool
   */
  public function get( array $postTypes, array $postTypesUsingWpEditor ) : bool;


}
