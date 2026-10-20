import "./Input.scss"

const Input = (props) => {

    if (props.type === "text") {

        return (
            <div className="input-text">
                <label>{props.label}</label>
                <input type="text" value={props.value} placeholder={props.placeholder} />
            </div>
        )
    }
    if (props.type === "email") {
        return (
            <div className="input-email">
                <label>{props.label}</label>
                <input className={props.className} type="email" value={props.value} placeholder={props.placeholder} />
            </div>
        )
    }
}
export default Input;