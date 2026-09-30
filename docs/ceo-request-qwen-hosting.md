> **File use case:** Approval checklist for hosting the intended ExecPlus model and preparing for customers.
> **What it does:** Separates immediate Qwen trial needs from mandatory pre-production resources and reviews.

# CEO request: Qwen3-4B hosting

Update 2026-09-28: VPS access, a 16 GiB P100 GPU, separate application/data folders,
Qwen trials and private eight-user demo deployment are now available. The current
deployment uses Qwen3-4B Q4_K_M; public domain/login, representative model quality
and the remaining customer-launch checks are still deferred. The original request
below remains useful for budget/privacy decisions, but hosting access is no longer
blocked. See the [current VPS runbook](vps-demo-runbook.md).

Recorded 2026-09-17: the intended model candidate is `Qwen/Qwen3-4B`, with a
hosting service still being arranged. It has not been tested in ExecPlus yet.
DeepSeek V4 Pro remains the current demo provider until the hosted Qwen service
is connected and passes evaluation. This records a preference, not a production
selection or authorization to purchase hosting.

## Ask for now

- [ ] **A hosting trial and spending limit.** Approve a short paid trial and a
  maximum monthly budget. Ask for setup, running, idle and storage charges.
- [ ] **A service that runs Qwen3-4B for us.** Ask whether the quote includes model
  setup, updates and support, or only a rented GPU server that we must operate.
- [ ] **Connection details for the development team.** The host should supply a
  secure API address, API key through a secure channel, deployed model name and
  a technical support contact. Keep the hosting account under company control.
- [ ] **An initial usage target.** Agree how many people will use it at the same
  time and how quickly answers should arrive. Let the provider size the server
  against those targets and verify its quote in the trial.
- [ ] **Written data-handling terms.** Confirm the server country, who can access
  requests, whether requests are stored or used for training, and how deletion
  works. Third-party hosting does not automatically make customer data private.

## Give this technical note to the hosting provider

Please quote managed hosting for the exact model `Qwen/Qwen3-4B`. Identify any
proposed alternative version or quantization (a compressed model) explicitly.
Provide authenticated HTTPS access to an OpenAI-compatible chat-completions API,
with structured JSON output, bounded response lengths and configurable thinking
mode. Qwen's [official model card](https://huggingface.co/Qwen/Qwen3-4B) documents
OpenAI-compatible serving through vLLM or SGLang; compatibility with our required
request fields must still be tested on your deployment.

Include the GPU and memory offered, supported request length, simultaneous-request
capacity, cold-start behavior, availability/support terms and all billing units.
Hardware requirements depend on model precision, request length and concurrency;
the model download size alone is not a server-sizing recommendation.

## Arrange before real customers

- [ ] **Approved example business documents and a reviewer.** Someone supplies
  documents we have permission to use, removes sensitive details where needed,
  and checks expected answers. Fictional demo documents are sufficient for now.
- [ ] **Hosting for the application and its data.** The website, API, database
  and uploaded files also need hosting, access controls, monitoring and tested
  backups. Confirm whether the model-hosting quote includes any of these.
- [ ] **Company email delivery access.** A verified sender/domain and an email
  service are needed for scheduled reports, followed by a real delivery test.
- [ ] **A release owner and time for final checks.** Production sign-in,
  permissions, data privacy, recovery and performance need documented review.

Engineering will compare hosted Qwen with the current demo provider for answer
quality, structured responses, speed and measured cost before recommending a
switch. Provider-specific settings, including thinking controls, must be verified;
copying the DeepSeek settings is not sufficient. Document-search model and vector
storage evaluation remain separate work. Hosting Qwen externally does not itself
complete a local-versus-hosted evaluation.

All existing [production gates](production-readiness.json) remain open until their
required evidence is reviewed. This checklist changes no phase-completion status.

## Message to the CEO

Please approve a managed-hosting trial for Qwen3-4B and set a monthly spending
limit. We need the provider to give our developers secure connection details,
support, a clear price and written data-privacy terms. We will test accuracy and
speed before committing to it. Before customer launch, we will also need app/data
hosting with backups, company email delivery and a business reviewer to validate
answers against approved sample documents. We can continue using demo documents
and DeepSeek while Qwen hosting is arranged.
