<?php

namespace WPML\Core\Component\MinimumRequirements\Application\Service;

use Throwable;
use WPML\Core\Component\MinimumRequirements\Domain\Entity\RequirementBase;
use WPML\Core\SharedKernel\Component\Server\Domain\CacheInterface;
use WPML\PHP\Exception\InvalidArgumentException;

/**
 * Class RequirementsService
 * Main service for checking and managing system requirements.
 */
class RequirementsService {

  /**
   * @var RequirementBase[]
   */
  private $requirements = [];

  /**
   * @var CacheInterface
   */
  private $cache;

  const CACHE_KEY = 'wpml_requirements';

  const CACHE_TTL = 60 * 10;


  /**
   * RequirementsService constructor.
   *
   * @param RequirementBase[] $requirements Array of requirement entities.
   * @param CacheInterface    $cache
   *
   * @throws InvalidArgumentException When any element in $requirements is not an instance of RequirementBase.
   */
  public function __construct( array $requirements, CacheInterface $cache ) {
    foreach ( $requirements as $requirement ) {
      if ( ! $requirement instanceof RequirementBase ) {
        throw new InvalidArgumentException( 'All requirements must be instances of RequirementBase' );
      }
    }

    $this->requirements = $requirements;
    $this->cache        = $cache;
  }


  /**
   * Gets all requirements as array
   *
   * @param bool $useCache
   *
   * @return array{
   *   id: int,
   *   isValid: bool,
   *   title: string,
   *   messages: array<array{
   *     type: string,
   *     message: string
   *   }>,
   * }[] Array of requirement data as associative arrays.
   * @throws Throwable
   */
  public function getAllRequirements( bool $useCache = false ): array {
    if ( $useCache ) {
      $cached = $this->cache->get( self::CACHE_KEY );

      if ( is_array( $cached ) ) {
        return $cached;
      }
    }

    $output = [];
    foreach ( $this->requirements as $requirement ) {
      $output[] = $requirement->toArray();
    }

    $this->cache->set( self::CACHE_KEY, $output, self::CACHE_TTL );

    return $output;
  }


  /**
   * Gets invalid requirements as array.
   *
   * @param bool $useCache
   *
   * @return array{
   *   id: int,
   *   isValid: bool,
   *   title: string,
   *   messages: array<array{
   *     type: string,
   *     message: string
   *   }>,
   * }[] Array of requirement data as associative arrays.
   * @throws Throwable
   */
  public function getInvalidRequirements( bool $useCache = false ): array {
    return array_values(
      array_filter(
        $this->getAllRequirements( $useCache ),
        function ( $requirement ) {
          return ! $requirement['isValid'];
        }
      )
    );
  }


}
