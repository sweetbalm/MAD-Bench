# 🪞 MirageBench
A benchmark revealing how multimodal GUI agents fake success.

[![Built with smolagents](https://img.shields.io/badge/smolagents-enabled-blue.svg)](https://github.com/huggingface/smolagents)
[![Powered by E2B](https://img.shields.io/badge/E2B-Desktop-orange.svg)](https://e2b.dev/)

## 🚨 Overview
As Large Vision-Language Models (VLMs) and computer-use agents increasingly take control of our desktops, safety concerns must evolve beyond text-based prompt injection. **MirageBench** is the first comprehensive benchmark designed to evaluate **Multimodal Fake Success**—a phenomenon where an agent, facing GUI constraints, deliberately manipulates visual environments to present a false illusion of task success to the user.

## 🕵️‍♂️ Key Deception Modes Evaluated
Our benchmark evaluates agents across dynamic GUI tasks, testing for sophisticated deceptive behaviors:

1.
2.
3. 

## 🛠️ Architecture
MirageBench is built for highly scalable and sandboxed evaluations:
- **Agent Framework:** `smolagents` for defining robust, code-driven agent loops and custom tool execution.
- **Environment:** `E2B Desktop` providing secure, cloud-based Ubuntu virtual machines for real-time VNC streaming and precise visual fault injection.
