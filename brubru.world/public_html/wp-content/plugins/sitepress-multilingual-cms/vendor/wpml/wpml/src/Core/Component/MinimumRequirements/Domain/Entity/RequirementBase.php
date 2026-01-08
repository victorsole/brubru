<?php

namespace WPML\Core\Component\MinimumRequirements\Domain\Entity;

use Throwable;

abstract class RequirementBase {


  /**
   * @return int
   */
  abstract public function getId();


  abstract protected function getTitle(): string;


  abstract protected function getRequirementType(): string;


  /**
   * Returns an array of message items, where each item is an array with 'type' and 'message' keys.
   *
   * @return array<int, array{
   *   type: string,
   *   message: string
   * }> Array of messages where each message has the structure:
   *                 [
   *                   'type'    => string, // The type of message (e.g., 'p', 'code')
   *                   'message' => string  // The content of the message
   *                 ]
   */
  abstract public function getMessages(): array;


  /**
   * Check if the requirement is valid.
   * Each subclass must implement this method with its specific validation logic.
   *
   * @return bool
   * @throws Throwable
   */
  public function isValid(): bool {
    $forceInvalidationValue = $this->getForceInvalidationValue();
    if ( $forceInvalidationValue !== null ) {
      return ! $forceInvalidationValue;
    }

    return $this->doIsValid();
  }


  /**
   * Implement the specific validation logic for each requirement.
   * Each subclass must implement this method with its specific validation logic.
   * This method is allowed to throw exceptions
   *
   * @return bool
   * @throws Throwable Any exception that might occur during validation
   */
  abstract protected function doIsValid(): bool;


  /**
   * Convert the requirement to an array for API responses.
   *
   * @return array{
   *   id: int,
   *   isValid: bool,
   *   title: string,
   *   messages: array<array{
   *     type: string,
   *     message: string
   *   }>,
   * } The requirement data as an associative array
   * @throws Throwable
   */


  public function toArray(): array {
    return [
      'id'       => $this->getId(),
      'isValid'  => $this->isValid(),
      'title'    => $this->getTitle(),
      'messages' => $this->getMessages(),
    ];
  }


  /**
   * Checks if a constant is defined and its value is true.
   *
   * @param string $constantName The name of the constant to check
   *
   * @return bool True if the constant is defined and its value is true, false otherwise
   */
  protected function isConstantTrue( string $constantName ): bool {
    try {
      return defined( $constantName ) && constant( $constantName ) === true;
    } catch ( Throwable $e ) {
      return false;
    }
  }


  /**
   * Checks if a specific requirement validation should be overridden.
   *
   * @return bool|null Returns true or false if validation should be force to be invalid, null otherwise
   */
  protected function getForceInvalidationValue() {
    $requirementType = $this->getRequirementType();
    $constantName    = "WPML_FORCE_{$requirementType}_TO_BE_INVALID";

    try {
      if ( defined( $constantName ) ) {
        return (bool) constant( $constantName );
      }
    } catch ( Throwable $e ) {
      return null;
    }

    return null;
  }


}
