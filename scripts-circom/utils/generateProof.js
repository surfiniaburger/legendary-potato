    // scripts-circom/utils/generateProof.js (Corrected Version)

    const snarkjs = require("snarkjs");
    const path = require("path");
    const fs = require("fs");
    require("dotenv").config();

    const circuitName = process.env.CIRCUIT_NAME;

    const generateProof = async (inputs) => {
        // We now use the 'inputs' object that we pass from main.js
        // instead of a placeholder.
        const { proof, publicSignals } = await snarkjs.groth16.fullProve(
            inputs,
            path.join(__dirname, `../../outputs/${circuitName}_js/${circuitName}.wasm`),
            path.join(__dirname, `../../outputs/keys/${circuitName}_final.zkey`)
        );

        console.log("Proof generated successfully!");

        // Save the proof and public signals to files
        const verifyDir = path.join(__dirname, "../../outputs/verify");
        if (!fs.existsSync(verifyDir)) {
            fs.mkdirSync(verifyDir);
        }
        fs.writeFileSync(path.join(verifyDir, `${circuitName}_proof.json`), JSON.stringify(proof, null, 1));
        fs.writeFileSync(path.join(verifyDir, `${circuitName}_public.json`), JSON.stringify(publicSignals, null, 1));

        return { proof, publicSignals };
    };

    module.exports = {
        generateProof,
    };