<?php

namespace WPML\UserInterface\Web\Infrastructure\CompositionRoot\Config\Updates;

use WPML\Core\Port\Update\UpdateInterface;
use WPML\PHP\Exception\RuntimeException;


class Update {

  /** @var int $id */
  private $id;

  /** @var class-string<UpdateInterface> $handlerClassName */
  private $handlerClassName;

  /**
   * @var callable|null $createHandler
   * @psalm-var callable(): UpdateInterface|null
   */
  private $createHandler;

  /** @var UpdateInterface|null $handler */
  private $handler;

  /** @var bool $tryOnlyOnce */
  private $tryOnlyOnce = false;

  /** @var bool $lazyLoad */
  private $lazyLoad = false;


  /**
   * @param int $id
   * @param class-string<UpdateInterface> $handlerClassName
   */
  public function __construct( $id, $handlerClassName ) {
    $this->id = $id;
    $this->handlerClassName = $handlerClassName;
  }


  public function id(): int {
    return $this->id;
  }


  /** @return class-string<UpdateInterface> */
  public function handlerClassName() {
    return $this->handlerClassName;
  }


  /**
   * @param callable $createHandler
   * @psalm-param callable(): UpdateInterface $createHandler
   *
   * @return void
   */
  public function setCreateHandler( $createHandler ) {
    $this->createHandler = $createHandler;
  }


  /**
   * @return UpdateInterface
   * @throws RuntimeException
   */
  public function handler() {
    if ( ! $this->handler ) {
      if ( ! $this->createHandler ) {
        throw new RuntimeException( 'No handler factory defined for update.' );
      }
      $create = $this->createHandler;
      $this->handler = $create();
    }

    return $this->handler;
  }


  public function tryOnlyOnce(): bool {
    return $this->tryOnlyOnce;
  }


  /** @return void */
  public function setTryOnlyOnce( bool $tryOnlyOnce ) {
    $this->tryOnlyOnce = $tryOnlyOnce;
  }


  public function lazyLoad(): bool {
    return $this->lazyLoad;
  }


  /** @return void */
  public function setLazyLoad( bool $lazyLoad ) {
    $this->lazyLoad = $lazyLoad;
  }


}
