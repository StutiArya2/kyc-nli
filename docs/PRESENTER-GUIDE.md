# KYC-NLI: Plain-English Walkthrough

A presenter's guide. Every number here is real and reproducible; the language is deliberately plain.

## The problem

An Indian passport prints your name **twice**: once in your regional script — Hindi, Tamil, Bengali or Urdu — and once in English letters, in the machine-readable strip at the bottom.

A bank's computer has to answer one question: *is this the same person?* It usually does that by comparing the two spellings letter by letter.

That breaks constantly, for two reasons.

**There is no single correct English spelling of an Indian name.** চট্টোপাধ্যায় can be written Chatterjee, Chattopadhyay or Chatterji, and all of them are right. We measured how bad this gets: in Urdu, **98% of words have more than one accepted English spelling** — about four each, on average.

**The camera does not read perfectly.** A phone photo of a passport is blurry, and the scanner drops or mangles letters.

Put those together and the result is that **real people get rejected** — because a computer decided that two spellings of their own name belonged to two different people.

## What we built

Instead of asking *do these two strings match?*, we ask the computer a **yes / no / can't-tell** question:

> Looking at this whole document, is the claim "this person's surname is CHATTERJEE" true, false, or impossible to tell?

Three possible answers:

| Answer | What it means | What happens |
| --- | --- | --- |
| **Yes** | The document supports the claim | Approve |
| **No** | The document contradicts it | Reject |
| **Can't tell** | The document doesn't carry the information | **Send to a human** |

**The third answer is the whole idea.** Most systems only have yes and no, so when they can't tell, they guess — and guessing "no" rejects a real customer.

Ours has an explicit *I don't know, get a person to look at this.* That is not the model being unsure of itself; it means the document genuinely does not contain the evidence. A passport has no "place of issue" field, so a claim about one can never be settled from the passport, no matter how good the reader is.

## How it works, step by step

### Step 1 — We make up fake people

We invent 1,000 fake passport holders. Fake names, fake dates, fake passport numbers. **Nothing real** — collecting real ID documents is illegal.

### Step 2 — We give each one a passport

Each fake person gets a document with their name printed **twice**: once in their own script, once in English in the machine-readable strip. Those two lines are built properly, with the real checksum arithmetic that passports use — checked character-for-character against the official specimen in the ICAO standard.

### Step 3 — We damage it, the way a real camera would

We deliberately corrupt the text: drop letters, swap letters, add stray marks.

**We did not guess how much.** We took real text, printed it, blurred it like a phone photo, ran it through a real scanner, and measured what actually broke. Then we copied that.

This mattered more than expected. Our first guess assumed the scanner mostly *swaps* letters. It turns out a real scanner mostly *deletes* them — between 1.3 and 3.6 times as often as it swaps them, depending on how good the photo is. That is a bigger deal than it sounds: a swapped letter still leaves something to compare against, but a deleted one removes the evidence entirely.

### Step 4 — We write questions about each document

For each fake person we write 7 questions, grouped in sets of 3. Within a set, **the document stays exactly the same and only the question changes**:

- "Is the surname Chatterjee?" → **Yes** (a valid alternative spelling)
- "Is the surname Mukherjee?" → **No** (a different person entirely)
- "Was it issued in Mumbai?" → **Can't tell** (the document doesn't say)

The sets of three are a **cheat detector**. A lazy system that just compares how similar two words look will get one of the three right and fail the others. We see that immediately instead of being fooled by a good average.

**Total: 7,000 questions across 5 languages**, built from 1,000 fake people.

### Step 5 — We test three systems on it

| System | What it does |
| --- | --- |
| **Exact match** | Compares letter by letter. This is roughly what banks use today. |
| **Rule engine** | A smart hand-written program. Knows the official spelling tables, checks the passport checksums, understands dates. |
| **AI model** | A small language model we trained ourselves. Sees only the damaged document and the question — no spelling tables, no hints. |

We deliberately made the rule engine as strong as we could. If our AI could only beat a weak system, we would have proved nothing.

## What is Dakshina?

**Dakshina is a free dataset published by Google Research in 2020.** It covers 12 South Asian languages, and we use four of them: Hindi, Tamil, Bengali and Urdu. It is about 2 GB, licensed CC BY-SA 4.0, and it is a download — not something we made.

**What is in it:** Google showed native speakers a word in their own script and asked them to *type it in English letters, however they would normally write it.* Different people wrote it differently. Dakshina records every answer.

So each row is one native word, one English spelling, and how many people wrote it that way:

```
अंक      ank      5
अंक      anka     1
अंकित    ankit    3
अंकों     ankon    2
अंकों     ankhon   1
अंकों     anakon   1
```

That is the key thing: **the spellings were written by actual humans, not generated by a rule.** Roughly 30,000 words per language.

### Why we needed it

The entire project rests on one claim: *there is no single correct English spelling of an Indian name.* Before Dakshina, our evidence for that was **three hand-picked examples in a slide**. A reviewer would rightly ask how we knew it was a real, general problem rather than three cherry-picked oddities.

Dakshina turns that claim into a measurement:

| Language | Average English spellings per word | Words with **more than one** spelling |
| --- | --- | --- |
| Hindi | 1.77 | 57% |
| Tamil | 2.72 | 75% |
| Bengali | 3.77 | 90% |
| **Urdu** | **4.25** | **98%** |

We had *predicted* that ordering in a design note before we looked at the data — Hindi least ambiguous, Urdu worst, because Urdu script doesn't write short vowels at all. Predicting it and then measuring it is a much stronger position than either on its own.

### The second, more uncomfortable job it did

We also used Dakshina to **mark our own homework**, and it caught us out.

We had been reporting how good our spelling converter was by testing it against 40 example pairs. For Urdu we were claiming **98% accuracy**. But we had *written those 40 pairs ourselves*, and had used them to build the converter in the first place — so we were grading an exam we had also set.

Tested against Dakshina's independent data, the real figure for Urdu was **29.5%**.

That is a big drop and it went straight into the write-up. It also pointed at two genuine bugs, which we fixed — one of which took Urdu from 9% to about 30%.

### One thing it is *not*

Dakshina is general vocabulary from Wikipedia — ordinary words, not a list of people's names. Names are in there, but not labelled as such, and everything is lowercase so we can't filter for them.

So we use Dakshina to **measure** our spelling converter, not to supply the names in our benchmark. If someone asks "why not just use real names from Dakshina?" — that is the honest answer, and finding a proper name list is a future milestone.

## Result 1 — the scoreboard

Tested on 1,050 questions about 150 fake people the AI had **never seen during training**.

| System | Gets it right | Real customers wrongly rejected | Sent to a human |
| --- | --- | --- | --- |
| Exact match (what banks use) | 27% | **89%** | 0% |
| Rule engine | 60% | 9% | 63% |
| **Our AI model** | **97%** | **6%** | **29%** |

Read the last column first. The rule engine only manages 60% accuracy **by sending 63 out of every 100 customers to a human being**.

Our model sends 29 — less than half — and is *both* more accurate *and* rejects fewer genuine people. Better on every measure at once, which was not guaranteed.

We ran a statistical test to check the gap isn't luck. It isn't.

### One detail worth mentioning if you have time

After the first round of training, the AI scored well on accuracy but was rejecting **more** real customers than the rule engine (17% vs 9%). It had bought its accuracy by being willing to make a call more often. A second round of training fixed that. Worth saying because it shows we were watching the right number, not just the headline one.

## Result 2 — the stronger argument

Someone will push back: *"Your AI just gives up less often. That's not better, that's a different setting."*

Fair challenge. So we flipped the question round:

> **Say you're only allowed to be wrong 5% of the time. How many customers must you send to a human?**

| System | To stay under 5% error |
| --- | --- |
| Exact match | **Impossible** |
| Rule engine | **Impossible** — it cannot get there no matter what you do |
| **Our AI** | **29 out of 100** — and it's already there by default |

The rule engine *physically cannot* be tuned to that accuracy. Even sending 93 out of 100 people to a human, it is still 5.2% wrong.

### Why — and this is the interesting bit

**The rule engine doesn't know when it's unsure.** Its confidence numbers were typed in by hand by whoever wrote each rule — 0.99 here, 0.85 there. They record *which rule fired*, not *how likely that rule is to be right*. So there's no dial to turn.

**The AI genuinely knows when it's unsure.** That means you can turn a dial: want fewer mistakes? Send a few more cases to a human, and the error rate actually drops. Tighten it to 2% error and it *still* handles about two-thirds of all traffic automatically — and that setting was chosen on separate practice data, not tuned on the exam.

So the sharpest version of the finding is not "our model scores higher". It is:

> **Only one of these two systems can be tuned to a business requirement at all.**

That is the line to end on if you only have one slide.

## The mistake we caught

**Tell this story. It makes the other numbers believable.**

Our first result was **99%**. It was wrong, and we worked out why.

Each fake person generated 3 sets of questions. When we split the data into "practice" and "exam", we accidentally split it by *question set* instead of by *person*. So the same fake person's passport ended up on both sides.

**94% of the people in the exam had already been seen during practice.** The AI wasn't reasoning. It was remembering.

What gave it away: one category came back at a perfect 100%. That was too good, and it was the thread we pulled.

We fixed the split, added an automatic check that fails the build if it ever happens again, and the honest score came out at **97%**. We kept the broken version on disk, labelled "invalid", so nobody finds it later and believes it.

Two more problems turned up the same way:

- **The damage model was wrong in a way that made the task too easy** — we assumed swapped letters, reality is deleted letters. Fixing it dropped the rule engine's score from 83% to 60%, which is the honest number.
- **Tamil had a fake error rate** caused by an invisible character the scanner adds. Once handled, Tamil's error rate went from 7% to 0.1%.

**Why this belongs in the presentation:** it shows the numbers are trustworthy *because* we went looking for reasons they might not be. A project that reports only good news hasn't checked.

## Is the code any good?

**409 automated tests.** They exercise 87% of all the code. Everything passes; the code also passes a style checker and a type checker cleanly.

Writing those tests found **15 real bugs**. The ones worth mentioning out loud:

- **The passport checksum accepted letters it shouldn't** and produced convincing-looking nonsense. That matters because the rule engine treats a failed checksum as proof of damage — so we were handing it a false signal.
- **"JOSÉ" was being turned into "JOS"** — the accented letter was dropped instead of simplified to E. That silently creates exactly the false rejection the whole project exists to fix.
- **With a small dataset, the exam set came out empty** and nobody was told. A quick test run would have been scoring a model on nothing.
- **The type checker had never actually run.** It was exiting successfully having checked zero files.

**None of the 15 changed a published headline number.** We re-ran the full comparison after every fix to confirm that — which is itself the point of having the tests.

## What to admit before someone asks

Saying these first is stronger than being caught by them.

**1. All the documents are fake.** No real passport was used. Collecting them is illegal, and we would not have been allowed to.

**2. But the hard parts are not fake.** The English spellings come from real people typing them (Dakshina). The camera damage was measured from a real scanner, not invented. The passport checksums are the genuine international standard.

**3. No human has checked the answers.** The "correct" answers come from our own generator, so we are grading against our own construction. Getting people to label a sample independently is the next milestone, and it is the real ceiling on every number here.

**4. Real photos are worse than ours.** We printed text and blurred it — no glare, no creases, no thumb over the corner, no worn-out passport. So real-world damage is worse than what we tested. Our numbers are a best case.

If you only have breath for one: **number 3**. It is the one a good examiner will find.

## The one-sentence version

> Banks reject real customers because their name is spelled two different ways on the same passport. We reframed the check as a **yes / no / can't-tell** question, and a small AI model cut the cases needing a human from **63 in 100 down to 29** — while rejecting **fewer** genuine customers, not more.

### If you want to show it running

The live walkthrough takes about a minute and has five parts: the problem → three answers not two → how bad it really is → the three systems scored live → the finding.

```
.\demo.ps1
```

**First `cd` into the project folder**, `C:\Users\HP\Desktop\projects\NLP\kyc-nli`. The `.\.venv\Scripts\` prefix is not optional — the tool lives inside the project's virtual environment, not on the system PATH, so a bare `kyc-nli ...` gives *"not recognized as the name of a cmdlet"*.

Other things you can run on the spot if challenged:

| If they ask | Run |
| --- | --- |
| "Show me a real example" | `.\.venv\Scripts\kyc-nli.exe inspect --language ta -n 2` |
| "Is that difference real or noise?" | `.\demo.ps1 -Bootstrap 1000` |
| "Isn't that just a different setting?" | `.\.venv\Scripts\kyc-nli.exe risk-coverage` |
| "Why these five languages?" | `.\.venv\Scripts\kyc-nli.exe languages` |
| "Show me the full breakdown" | `.\.venv\Scripts\kyc-nli.exe run-baseline rule_engine` |
| "Can I try it myself?" | `.\.venv\Scripts\kyc-nli.exe serve` — opens the interactive explorer |

### The three numbers to memorise

- **63 → 29** — cases needing a human, before and after
- **98%** — of Urdu words have more than one correct English spelling
- **94%** — the overlap bug we caught in our own first result
