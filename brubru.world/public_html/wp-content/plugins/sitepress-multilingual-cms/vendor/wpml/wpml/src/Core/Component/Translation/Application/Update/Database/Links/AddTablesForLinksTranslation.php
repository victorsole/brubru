<?php

namespace WPML\Core\Component\Translation\Application\Update\Database\Links;

use WPML\Core\Component\Translation\Domain\Links\RepositoryInterface;
use WPML\Core\Port\Update\UpdateInterface;
use WPML\PHP\Exception\Exception;

class AddTablesForLinksTranslation implements UpdateInterface {

  /** @var RepositoryInterface */
  private $repository;


  public function __construct( RepositoryInterface $repository ) {
    $this->repository = $repository;
  }


  public function update() {
    try {
      return $this->repository->addDatabaseTablesIfNotExist();
    } catch ( Exception $e ) {
      return false;
    }
  }


}
