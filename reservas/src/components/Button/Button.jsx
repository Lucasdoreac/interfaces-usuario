import "./Button.scss"

const ButtonComponent = (props) => {
    const className = [
        "btn",
        props.variant && `btn-${props.variant}`,
        props.size && `btn-${props.size}`,
        props.style,
    ].filter(Boolean).join(" ");

    if (props.href) {
        return <a href={props.href} className={className}>{props.text}</a>;
    }

    return <button type={props.type || "button"} className={className}>{props.text}</button>;
}

export default ButtonComponent;
