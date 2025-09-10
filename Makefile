-include .env

.PHONY: all plonk-fflonk skip list new-tau contribute-tau-first contribute-tau-second create-challenge contribute-challenge import-response verify-tau apply-beacon-tau prepare-phase2 verify-final-tau compile info setup-export-key setup-groth16-key contribute-zkey-first contribute-zkey-second exportkey-mpcparams-bellman contribute-bellman import-bellman-response verify-zkey-third-contributions apply-beacon-zkey verify-zkey-final final-zkey-export generate-proof-verify generate-verifier solidity-calldata test clean clean-all

all:
	@if [ -f power-of-tau/pot12_final.ptau ]; then \
		echo "pot12_final.ptau exists in power-of-tau/"; \
		$(MAKE) verify-final-tau compile info setup-groth16-key contribute-zkey-first contribute-zkey-second exportkey-mpcparams-bellman contribute-bellman import-bellman-response verify-zkey-third-contributions apply-beacon-zkey verify-zkey-final final-zkey-export generate-proof-verify generate-verifier solidity-calldata test; \
	else \
		echo "pot12_final.ptau does not exist in power-of-tau/"; \
		$(MAKE) new-tau contribute-tau-first contribute-tau-second create-challenge contribute-challenge import-response verify-tau apply-beacon-tau prepare-phase2 verify-final-tau compile info setup-groth16-key contribute-zkey-first contribute-zkey-second exportkey-mpcparams-bellman contribute-bellman import-bellman-response verify-zkey-third-contributions apply-beacon-zkey verify-zkey-final final-zkey-export generate-proof-verify generate-verifier solidity-calldata test; \
	fi

plonk-fflonk: new-tau contribute-tau-first contribute-tau-second create-challenge contribute-challenge import-response verify-tau apply-beacon-tau prepare-phase2 verify-final-tau compile info setup-export-key generate-proof-verify generate-verifier solidity-calldata test

# Skip when u already have powersoftau files and you want to skip the phase 2 ceremony
skip: compile info setup-export-key generate-proof-verify generate-verifier solidity-calldata test

# ===============================================================
# OUR CUSTOM HACKATHON WORKFLOW
# This rule does everything we need to build and test our project.
# ===============================================================

hackathon:
	@echo "--- (1/8) Compiling Circuit ---"
	@make compile CIRCUIT_NAME=$(CIRCUIT_NAME)
	@echo "\n--- (2/8) Generating ZKP Keys ---"
	@make setup-export-key CIRCUIT_NAME=$(CIRCUIT_NAME)
	@echo "\n--- (3/8) Generating Solidity Verifier ---"
	@make generate-verifier CIRCUIT_NAME=$(CIRCUIT_NAME)
	@echo "\n--- (4/8) Generating Proof ---"
	@make generate-proof-verify CIRCUIT_NAME=$(CIRCUIT_NAME)
	@echo "\n--- (5/8) Generating Solidity Calldata for Test ---"
	@make solidity-calldata CIRCUIT_NAME=$(CIRCUIT_NAME)
	@echo "\n--- (6/8) Formatting Solidity Code ---"
	@forge fmt
	@echo "\n--- (7/8) Cleaning Foundry Cache ---"
	@forge clean
	@echo "\n--- (8/8) Running Smart Contract Tests ---"
	@forge test

# # Inspect the circuit
# inspect:
# 	@circomspect ./circuits/$(CIRCUIT_NAME).circom

# List all available circuits
list:
	@echo "Available circuits:" && ls circuits/*.circom | xargs -n 1 basename | sed "s/\.circom//"

# # Check whether it compiles
# check:
# 	@circom ./circuits/*.circom -l node_modules

# inspect-sarif:
# 	@circomspect circuits/$(CIRCUIT_NAME).circom --sarif-file circuits/sarif-results.sarif

# Create a new powersoftau file
new-tau:
	@npx snarkjs powersoftau new $(ELLIPTIC_CURVE) $(POWER_OF_TAU) power-of-tau/pot$(POWER_OF_TAU)_0000.ptau

# Contribute to the powersoftau file
contribute-tau-first:
	@npx snarkjs powersoftau contribute power-of-tau/pot$(POWER_OF_TAU)_0000.ptau power-of-tau/pot$(POWER_OF_TAU)_0001.ptau --name="First contribution"

contribute-tau-second:
	@npx snarkjs powersoftau contribute power-of-tau/pot$(POWER_OF_TAU)_0001.ptau power-of-tau/pot$(POWER_OF_TAU)_0002.ptau --name="Second contribution"

create-challenge:
	@npx snarkjs powersoftau export challenge power-of-tau/pot$(POWER_OF_TAU)_0002.ptau power-of-tau/challenge/challenge_0003

contribute-challenge:
	@npx snarkjs powersoftau challenge contribute $(ELLIPTIC_CURVE) power-of-tau/challenge/challenge_0003 power-of-tau/challenge/response_0003

import-response:
	@npx snarkjs powersoftau import response power-of-tau/pot$(POWER_OF_TAU)_0002.ptau power-of-tau/challenge/response_0003 power-of-tau/pot$(POWER_OF_TAU)_0003.ptau -n="Third contribution name"

# U still need to prepare for this ptau file to be used in the phase 2 ceremony
verify-tau:
	@npx snarkjs powersoftau verify power-of-tau/pot$(POWER_OF_TAU)_0003.ptau

# Apply a random beacon in order to finalize phase 1 of the trusted setup
# Iterations is the number of iterations of hash function
apply-beacon-tau:
	@npx snarkjs powersoftau beacon power-of-tau/pot$(POWER_OF_TAU)_0003.ptau power-of-tau/pot$(POWER_OF_TAU)_beacon.ptau $(BEACON_TAU) $(ITERATIONS_TAU) -n="Final Beacon"

# Prepare Phase 2
prepare-phase2:
	@npx snarkjs powersoftau prepare phase2 power-of-tau/pot$(POWER_OF_TAU)_beacon.ptau power-of-tau/pot$(POWER_OF_TAU)_final.ptau

# Verify the final ptau file
verify-final-tau:
	@npx snarkjs powersoftau verify power-of-tau/pot$(POWER_OF_TAU)_final.ptau

# Compile the circuit
compile:
	@echo "--- Compiling Circuit: $(CIRCUIT_NAME) ---"
	@circom ./circuits/$(CIRCUIT_NAME).circom --r1cs --wasm --sym -o ./outputs -l ./node_modules

info:
	@npx snarkjs r1cs info ./outputs/$(CIRCUIT_NAME).r1cs

# Trusted setup and export the verifiaction key (If you are using Groth16 in production, you should contribute to the zkey, not using this command which exports the verification key directly (insecure for Groth16, but ok for PlonK and FFlonk))
# If u r using PlonK or FFlonk, you can use this command to export the verification key directly and skip to generate-proof-verify (which skips the trusted setup contributions)
setup-export-key:
	@npx snarkjs $(TYPE_OF_SNARK) setup ./outputs/$(CIRCUIT_NAME).r1cs power-of-tau/pot$(POWER_OF_TAU)_final.ptau ./outputs/keys/$(CIRCUIT_NAME)_final.zkey && npx snarkjs zkey verify ./outputs/$(CIRCUIT_NAME).r1cs power-of-tau/pot$(POWER_OF_TAU)_final.ptau ./outputs/keys/$(CIRCUIT_NAME)_final.zkey && npx snarkjs zkey export verificationkey ./outputs/keys/$(CIRCUIT_NAME)_final.zkey ./outputs/keys/$(CIRCUIT_NAME)_verification_key.json

# Follow here if u r using Groth16
# Creates an initial groth16 pkey file with zero contributions
setup-groth16-key:
	@npx snarkjs groth16 setup ./outputs/$(CIRCUIT_NAME).r1cs power-of-tau/pot$(POWER_OF_TAU)_final.ptau ./outputs/keys/$(CIRCUIT_NAME)_0000.zkey

contribute-zkey-first:
	@npx snarkjs zkey contribute ./outputs/keys/$(CIRCUIT_NAME)_0000.zkey ./outputs/keys/$(CIRCUIT_NAME)_0001.zkey --name="1st Contributor Name"

contribute-zkey-second:
	@npx snarkjs zkey contribute ./outputs/keys/$(CIRCUIT_NAME)_0001.zkey ./outputs/keys/$(CIRCUIT_NAME)_0002.zkey --name="Second contribution Name"

# Export a zKey to a MPCParameters file compatible with kobi/phase2 (Bellman)
exportkey-mpcparams-bellman:
	@npx snarkjs zkey export bellman ./outputs/keys/$(CIRCUIT_NAME)_0002.zkey ./outputs/keys/challenge/$(CIRCUIT_NAME)_challenge_phase2_0003

contribute-bellman:
	@npx snarkjs zkey bellman contribute $(ELLIPTIC_CURVE) ./outputs/keys/challenge/$(CIRCUIT_NAME)_challenge_phase2_0003 ./outputs/keys/challenge/$(CIRCUIT_NAME)_response_phase2_0003

import-bellman-response:
	@npx snarkjs zkey import bellman ./outputs/keys/$(CIRCUIT_NAME)_0002.zkey ./outputs/keys/challenge/$(CIRCUIT_NAME)_response_phase2_0003 ./outputs/keys/$(CIRCUIT_NAME)_0003.zkey -n="Third contribution name"

# Verify zkey file contributions and verify that matches with the original circuit.r1cs and ptau (for latest zkey after three contributions)
verify-zkey-third-contributions:
	@npx snarkjs zkey verify ./outputs/$(CIRCUIT_NAME).r1cs power-of-tau/pot$(POWER_OF_TAU)_final.ptau ./outputs/keys/$(CIRCUIT_NAME)_0003.zkey

# Apply a random beacon in order to finalize phase 2 of the trusted setup
apply-beacon-zkey:
	@npx snarkjs zkey beacon ./outputs/keys/$(CIRCUIT_NAME)_0003.zkey ./outputs/keys/$(CIRCUIT_NAME)_final.zkey $(BEACON_ZKEY) $(ITERATIONS_ZKEY) -n="Final Beacon phase2"

verify-zkey-final:
	@npx snarkjs zkey verify ./outputs/$(CIRCUIT_NAME).r1cs power-of-tau/pot$(POWER_OF_TAU)_final.ptau ./outputs/keys/$(CIRCUIT_NAME)_final.zkey

# Export the verification key for the final zkey
final-zkey-export:
	@npx snarkjs zkey export verificationkey ./outputs/keys/$(CIRCUIT_NAME)_final.zkey ./outputs/keys/$(CIRCUIT_NAME)_verification_key.json

# Generate the proof and public inputs and then verify the proof
generate-proof-verify:
	@node ./scripts-circom/main.js

# Generate the verifier contract
generate-verifier:
	npx snarkjs zkey export solidityverifier ./outputs/keys/$(CIRCUIT_NAME)_final.zkey ./src/$(CIRCUIT_NAME)_Verifier.sol

# Generate the solidity calldata for the proof
solidity-calldata:
	npx snarkjs zkey export soliditycalldata ./outputs/verify/$(CIRCUIT_NAME)_public.json ./outputs/verify/$(CIRCUIT_NAME)_proof.json

# Verify the proof wih the verification key
test:
	npx snarkjs groth16 verify ./outputs/keys/$(CIRCUIT_NAME)_verification_key.json ./outputs/verify/$(CIRCUIT_NAME)_public.json ./outputs/verify/$(CIRCUIT_NAME)_proof.json

# Clean the outputs directory and remove the generated files
clean:
	@rm -rf ./outputs/$(CIRCUIT_NAME)_js && rm ./outputs/verify/*.json ./circuits/sarif-results.sarif ./outputs/keys/$(CIRCUIT_NAME)_final.zkey ./outputs/keys/$(CIRCUIT_NAME)_verification_key.json ./outputs/keys/challenge/$(CIRCUIT_NAME)_challenge_phase2_0003 ./outputs/keys/challenge/$(CIRCUIT_NAME)_response_phase2_0003 ./outputs/$(CIRCUIT_NAME).sym ./outputs/$(CIRCUIT_NAME).r1cs src/$(CIRCUIT_NAME)_Verifier.sol

# Clean all outputs, including the powersoftau files and the verifier contract
clean-all:
	@rm -rf ./outputs/$(CIRCUIT_NAME)_js && rm ./outputs/verify/*.json ./circuits/sarif-results.sarif ./outputs/keys/*.zkey ./outputs/keys/$(CIRCUIT_NAME)_verification_key.json ./outputs/keys/challenge/* ./outputs/*.sym ./outputs/*.r1cs power-of-tau/challenge/* power-of-tau/*.ptau ./src/$(CIRCUIT_NAME)_Verifier.sol