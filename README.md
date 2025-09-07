# ZK-RedTeam: The "Janus" Proof of Audit Circuit

This repository contains the core Zero-Knowledge Proof engine for the **ZK-RedTeam** project, submitted to the OpenAI Open Model Hackathon. It is based on the `circom-startup` template.

Our central circuit, **"Janus"**, creates a verifiable "Proof of Audit." It proves that a specific, secret adversarial prompt was used to red team an AI model, without revealing the prompt itself. This allows for private, verifiable AI safety audits.

We are using `gpt-oss` to jailbreak itself and then using cryptography to *prove* that this kind of jailbreak is possible. We are using the model as both the poacher and the gamekeeper. 

![ZK RedTeam](flow.jpeg)

## Features

- **Janus Circuit**: A Circom circuit that proves knowledge of a 256-character string's preimage to a Poseidon hash.
- **Automated Workflow**: Uses the template's `Makefile` for streamlined compilation, key generation, and proof generation.
- **Groth16 Proving System**: Optimized for small proof sizes and fast verification.
- **Solidity Verifier Export**: Capable of generating a smart contract for on-chain verification of audits.

## Getting Started

### Prerequisites

- [Node.js](https://nodejs.org/) & [pnpm](https://pnpm.io/installation)
- [Foundry](https://book.getfoundry.sh/getting-started/installation) for smart contract development.
- **Rust & Cargo** for installing the Circom toolchain.
- Run `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh` to install Rust.
- **Circom Compiler**: Run `cargo install circom`.
- **snarkjs**: This is installed locally via `pnpm`. We will use `npx snarkjs`.

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/YOUR_USERNAME/ZK-RedTeam.git
    cd ZK-RedTeam/circom-scaffold
    ```

2.  **Install Node.js dependencies:**
    ```bash
    pnpm install
    ```

3.  **Download the Powers of Tau file:**
    The Janus circuit is large and requires a Powers of Tau ceremony file of at least power 16.
    ```bash
    mkdir -p power-of-tau
    wget https://storage.googleapis.com/zkevm/ptau/powersOfTau28_hez_final_16.ptau -O power-of-tau/pot16_final.ptau
    ```

### Configuration

1.  **Set the Circuit Name:**
    Copy `.env.example` to `.env` and set the following variables:
    ```
    CIRCUIT_NAME=Janus
    POWER_OF_TAU=16
    ```
    *(Note: Our main circuit file is located at `circuits/Janus.circom`)* similarly proof_of_prompt.circom

2.  **Set Your Private Input:**
    Open `scripts-circom/main.js` and replace the placeholder `promptString` with the secret you want to prove knowledge of.

### Usage

This template has been modified to work with the latest version of the Circom compiler.

**To generate a proof for the "Janus" circuit:**

```bash
make hackathon CIRCUIT_NAME=Janus
```

This single command will:
1.  Compile the `circuits/Janus.circom` circuit.
2.  Generate the proving and verification keys using the `pot16_final.ptau` file.
3.  Execute `scripts-circom/main.js` to:
    *   Take your secret prompt as a private input.
    *   Generate a valid `proof.json` and `public.json` (containing the prompt's hash).
4.  Run the verification script to confirm the proof is valid.

The final proof and public signals can be found in the `outputs/verify/` directory.

### Modifications for Modern Circom (v2.2.2+)

The original `circom-startup` template was built for an older version of Circom. To get it working, we made the following critical changes:

1.  **Removed `circomspect` and the `check` rule:** The `inspect` and `check` steps in the original `Makefile` were incompatible with the latest Circom compiler. We removed these steps and all their dependencies from the `Makefile` to streamline the build process.
2.  **Used `npx snarkjs`:** To ensure the `Makefile` uses the locally installed version of `snarkjs` from `node_modules`, all calls to `snarkjs` were replaced with `npx snarkjs`.
3.  **Updated Helper Scripts:** The files `scripts-circom/utils/generateProof.js` and `scripts-circom/utils/verify.js` were completely rewritten to correctly handle dynamic inputs and use the `groth16` proving system, fixing several hardcoded placeholders and logic bugs.
4.  **Corrected Circuit Logic:** The `Janus.circom` file was written to handle large inputs (256 bytes) by implementing iterative hashing, as the standard `Poseidon` library has a small input limit.

---

## License

This project is licensed under the MIT License.