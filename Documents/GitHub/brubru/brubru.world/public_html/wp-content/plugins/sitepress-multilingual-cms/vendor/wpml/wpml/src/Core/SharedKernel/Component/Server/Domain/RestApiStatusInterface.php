<?php

namespace WPML\Core\SharedKernel\Component\Server\Domain;

interface RestApiStatusInterface {


  public function isEnabled( bool $useCache = false ): bool;


  public function getEndpoint(): string;


}
