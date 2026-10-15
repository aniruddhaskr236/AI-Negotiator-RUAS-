export type CallStatus = "ringing" | "talking" | "done" | "failed" | "retrying"
export type Speaker = "agent" | "shop"
export type Language = "en" | "hi" | "kn"

export type TranscriptTurn = {
  speaker: Speaker
  text: string
  translation?: string
  lang: Language
  ts: string
}

export type Shop = {
  id: string
  name: string
  status: CallStatus
  first_price: number | null
  final_price: number | null
  warranty_months: number | null
  eta_days: number | null
  part_type: string
  conditions: string
  error?: string
  transcript: TranscriptTurn[]
}

export const job = {
  need: "iPhone 13 screen replacement, original part preferred",
  weights: { price: 40, warranty: 25, speed: 20, quality: 15 },
}

export const shops: Shop[] = [
  {
    id: "1",
    name: "Sri Ganesh Mobiles",
    status: "done",
    first_price: 4500,
    final_price: 3800,
    warranty_months: 6,
    eta_days: 1,
    part_type: "OEM",
    conditions: "GST extra",
    transcript: [
      {
        speaker: "agent",
        text: "Hello, I need a quote for an iPhone 13 screen replacement.",
        lang: "en",
        ts: "10:02:04",
      },
      {
        speaker: "shop",
        text: "An OEM screen replacement will be ₹4,500.",
        lang: "en",
        ts: "10:02:18",
      },
      {
        speaker: "agent",
        text: "दूसरी दुकान ने ₹3,900 कहा है। आपकी सबसे अच्छी कीमत क्या होगी?",
        translation: "Another shop quoted ₹3,900. What would be your best price?",
        lang: "hi",
        ts: "10:02:31",
      },
      {
        speaker: "shop",
        text: "I can reduce it to ₹4,200 for the OEM part.",
        lang: "en",
        ts: "10:02:48",
      },
      {
        speaker: "agent",
        text: "What warranty, GST terms, and turnaround do you offer?",
        lang: "en",
        ts: "10:03:02",
      },
      {
        speaker: "shop",
        text: "Final ₹3,800, OEM screen, six-month warranty, one-day turnaround. GST extra.",
        lang: "en",
        ts: "10:03:24",
      },
    ],
  },
  {
    id: "2",
    name: "Mobile Hub Indiranagar",
    status: "talking",
    first_price: 3900,
    final_price: null,
    warranty_months: 3,
    eta_days: 2,
    part_type: "Aftermarket",
    conditions: "",
    transcript: [
      {
        speaker: "agent",
        text: "I need an iPhone 13 screen replacement, preferably an original part.",
        lang: "en",
        ts: "10:06:01",
      },
      {
        speaker: "shop",
        text: "An aftermarket screen will be ₹3,900 with a three-month warranty.",
        lang: "en",
        ts: "10:06:10",
      },
      {
        speaker: "agent",
        text: "Can you provide an original or OEM screen instead?",
        lang: "en",
        ts: "10:06:17",
      },
      {
        speaker: "shop",
        text: "अभी ओरिजिनल स्क्रीन उपलब्ध नहीं है।",
        translation: "The original screen is not available right now.",
        lang: "hi",
        ts: "10:06:29",
      },
      {
        speaker: "shop",
        text: "How long will the repair take, and is GST included?",
        lang: "en",
        ts: "10:06:42",
      },
      {
        speaker: "agent",
        text: "The aftermarket part takes two days. I need to confirm GST and the final price.",
        lang: "en",
        ts: "10:06:56",
      },
    ],
  },
  {
    id: "3",
    name: "City Fix Corner",
    status: "failed",
    first_price: null,
    final_price: null,
    warranty_months: null,
    eta_days: null,
    part_type: "",
    conditions: "",
    error: "No answer after 2 tries",
    transcript: [
      {
        speaker: "agent",
        text: "Dialling City Fix Corner about an iPhone 13 screen replacement.",
        lang: "en",
        ts: "10:09:00",
      },
      { speaker: "shop", text: "No response.", lang: "en", ts: "10:09:31" },
      {
        speaker: "agent",
        text: "पहली कोशिश का जवाब नहीं मिला।",
        translation: "The first attempt was not answered.",
        lang: "hi",
        ts: "10:09:34",
      },
      {
        speaker: "agent",
        text: "Waiting 30 seconds before retry.",
        lang: "en",
        ts: "10:09:36",
      },
      {
        speaker: "agent",
        text: "Second attempt started for the screen repair quote.",
        lang: "en",
        ts: "10:10:06",
      },
      {
        speaker: "shop",
        text: "No response. Call ended.",
        lang: "en",
        ts: "10:10:38",
      },
    ],
  },
]

export const timelineEvents = [
  { time: "10:02", text: "Shop 1 opened at ₹4,500 for an OEM screen." },
  {
    time: "10:03",
    text: "Shop 1 dropped ₹4,500 to ₹4,200 after agent cited another quote.",
  },
  {
    time: "10:03",
    text: "Shop 1 closed at ₹3,800 with an OEM part and six-month warranty.",
  },
  {
    time: "10:06",
    text: "Shop 2 offered an aftermarket screen and did not confirm GST.",
  },
  { time: "10:10", text: "Shop 3 failed after two unanswered calls." },
]
