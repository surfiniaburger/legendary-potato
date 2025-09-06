// circuits/proof_of_prompt.circom (FINAL Corrected Version)
pragma circom 2.0.0;

// We still need the Poseidon library
include "circomlib/circuits/poseidon.circom";

// This circuit now correctly hashes a long input by breaking it into chunks.
template Hasher(n_inputs) {
    // The secret inputs to be hashed
    signal input in[n_inputs];
    // The single hash output
    signal output out;

    // We will hash 16 inputs at a time.
    var chunk_size = 15;
    var num_chunks = (n_inputs + chunk_size - 1) \ chunk_size;

    // Create an array of Poseidon hashers, one for each chunk
    component hashers[num_chunks];
    for (var i = 0; i < num_chunks; i++) {
        hashers[i] = Poseidon(chunk_size + 1);
    }

    // This will hold the intermediate hash results
    signal current_hash[num_chunks];

    // Now, we chain the hashes together
    for (var i = 0; i < num_chunks; i++) {
        // The first input to the hasher is the result of the previous hash.
        // For the very first chunk, we use 0.
        if (i == 0) {
            hashers[i].inputs[0] <== 0;
        } else {
            hashers[i].inputs[0] <== current_hash[i-1];
        }

        // The other inputs are the chunk of our prompt
        for (var j = 0; j < chunk_size; j++) {
            var input_idx = i * chunk_size + j;
            if (input_idx < n_inputs) {
                hashers[i].inputs[j+1] <== in[input_idx];
            } else {
                // Pad with zeros if we're at the end
                hashers[i].inputs[j+1] <== 0;
            }
        }
        
        // Store the result of this chunk's hash
        current_hash[i] <== hashers[i].out;
    }

    // The final output is the hash of the very last chunk
    out <== current_hash[num_chunks - 1];
}

// Our main component now uses the correct Hasher
template ProofOfPrompt() {
    signal input prompt[256];
    signal output prompt_hash;

    component h = Hasher(256);
    for (var i = 0; i < 256; i++) {
        h.in[i] <== prompt[i];
    }
    prompt_hash <== h.out;
}

component main = ProofOfPrompt();