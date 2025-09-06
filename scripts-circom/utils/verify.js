    // scripts-circom/utils/verify.js (Final Corrected Version)

    const snarkjs = require("snarkjs");
    const fs = require("fs");
    const path = require("path");
    require("dotenv").config(); // Make sure we can read from .env

    // Explicitly read the circuit name from the environment variables
    const circuitName = process.env.CIRCUIT_NAME;

    const verifyProof = async (proof, publicSignals) => {
        // Construct the correct path to the verification key
        const vkeyPath = path.join(__dirname, `../../outputs/keys/${circuitName}_verification_key.json`);
        const vKey = JSON.parse(fs.readFileSync(vkeyPath));

        // Use the correct proving system (groth16) for verification
        const res = await snarkjs.groth16.verify(vKey, publicSignals, proof);

        if (res === true) {
            console.log("\nProof verified successfully!");
        } else {
            console.log("\nInvalid proof!");
        }
    };

    module.exports = {
        verifyProof,
    };