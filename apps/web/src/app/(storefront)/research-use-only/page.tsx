import styles from "../legal.module.css";

export const metadata = { title: "Research Use Only" };

export default function ResearchUseOnlyPage() {
  return (
    <main className={styles.wrap}>
      <span className={`eyebrow ${styles.eyebrow}`}>Policy</span>
      <h1>Research Use Only</h1>
      <p className={styles.updated}>Last updated August 13, 2026</p>

      <p>
        Every product offered by TimeChain is sold strictly for laboratory and research use. By placing an order,
        you agree to the terms below.
      </p>

      <h2>Not for human or veterinary use</h2>
      <p>
        Products offered on this site are not drugs, dietary supplements, cosmetics, or food. They are not
        intended for human or veterinary use, and are not intended to diagnose, treat, cure, or prevent any
        disease or condition. Not for human consumption.
      </p>

      <h2>No medical claims</h2>
      <p>
        Nothing on this site is medical advice, and nothing on this site should be read as a claim about the
        safety, efficacy, or effect of any compound in humans or animals. Product listings describe sourcing and
        formulation only.
      </p>

      <h2>Buyer representations</h2>
      <p>By purchasing, you represent that:</p>
      <ul>
        <li>You are acquiring the product solely for legitimate laboratory or research purposes.</li>
        <li>You are at least 21 years of age.</li>
        <li>
          You are responsible for understanding and complying with all laws and regulations that apply to the
          purchase, possession, and use of research compounds in your jurisdiction.
        </li>
        <li>You will not resell, distribute, or represent these products as intended for human consumption.</li>
      </ul>

      <h2>Handling and safety</h2>
      <p>
        Research compounds should be handled only by qualified personnel, in an appropriate laboratory setting,
        using proper safety equipment and procedures.
      </p>
    </main>
  );
}
