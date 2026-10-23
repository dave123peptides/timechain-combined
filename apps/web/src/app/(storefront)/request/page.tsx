import RequestForm from "./RequestForm";

export const metadata = { title: "Your order request" };

// The order request page (B2B redesign, 2026-10-22): the request list
// with contact details, sent to the API as one order request. The form
// itself is a client component; this wrapper keeps the route a server
// page so metadata works.
export default function RequestPage() {
  return <RequestForm />;
}
