<?php

namespace WPML\Core\Component\MinimumRequirements\Domain\Entity;

use WPML\Core\SharedKernel\Component\Server\Domain\ServerInfoInterface;

class EvalFunctionRequirement extends RequirementBase {

  /** @var ServerInfoInterface */
  private $serverInfo;

  const EXTENSION_NAME = 'suhosin';


  /**
   * Constructor.
   *
   * @param ServerInfoInterface $serverInfo The server info service.
   */
  public function __construct( ServerInfoInterface $serverInfo ) {
    $this->serverInfo = $serverInfo;
  }


  public function getId(): int {
    return 8;
  }


  public function getTitle(): string {
    return __( 'PHP eval() Function', 'wpml' );
  }


  public function getMessages(): array {
    return [
      [
        'type'    => 'p',
        'message' => __(
          'The PHP eval() function is disabled by the Suhosin extension. ' .
          'WPML requires this function when Suhosin is enabled.',
          'wpml'
        ),
      ],
      [
        'type'    => 'alert',
        'message' => __(
          'Contact your hosting provider to enable the eval() function in' .
          ' the Suhosin configuration or disable the Suhosin extension.',
          'wpml'
        ),
      ]
    ];
  }


  protected function doIsValid(): bool {
    // Only check if eval is available when Suhosin is enabled
    if ( ! $this->serverInfo->isExtensionLoaded( self::EXTENSION_NAME ) ) {
      return true;
    }

      return ! filter_var(
        $this->serverInfo->getIniGet( 'suhosin.executor.disable_eval' ),
        FILTER_VALIDATE_BOOLEAN
      );
  }


  protected function getRequirementType(): string {
    return 'EVAL_FUNCTION';
  }


}
