// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test, console} from "forge-std/Test.sol";
import "src/Janus_Verifier.sol";

contract JanusTest is Test {
    Groth16Verifier public verifier;

    function setUp() public {
        verifier = new Groth16Verifier();
    }

    function test_VerifyProof_Succeeds() public {
        // This is the calldata from the last successful 'make' run,
        // with the double quotes removed so Solidity recognizes them as numbers.
        bool success = verifier.verifyProof(
            [
                0x1341a79fb730511a73209a886d4daa05b257a405d45df7d00501d22e9f3be384,
                0x141c863813581477bd147616818143183d9cb96805554e5b8f970dd335c332d8
            ],
            [
                [
                    0x2bc06b47de264098e2f50a0c811fdce5eecf6cb26b0e5d03ece7b88f19c4e814,
                    0x1d6832f4b12966fe8f2130cfb1d08591ac28195573c70c91f296e77d7e8cf04a
                ],
                [
                    0x0d1b7c6d872f7cdbc84be92ea4ed7ffd0ae4125bc9a1dd8cffe75ad45f4a9aea,
                    0x290e23d1fb83b65b2076693119c3fa0e6af33012c791979f63ea83fad2cc477d
                ]
            ],
            [
                0x2a91e1194642f66b827bc3b7d01bb3a0b37c55b3f1163583e2792c09d86e8762,
                0x0aa4dec05394d7df8c84fa5dc40b36ed57cabfd2777e03616bcbc064edb148a1
            ],
            [0x026cb3613b8e05f1f8cdf36c9ca42cdd183bc63490194ddf879410635517860f]
        );

        assertTrue(success);
    }
}
